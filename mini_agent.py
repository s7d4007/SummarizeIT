"""A small dependency-free text summarization agent."""

from __future__ import annotations

import argparse
import html
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


VERSION = "0.1.0"
OFFLINE_FALLBACK = "Please check your Internet Connection"
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "will", "with", "you", "your", "about", "also",
    "can", "could", "how", "may", "more", "such", "than", "then", "these",
    "those", "when", "where", "which", "while", "who", "would",
}
WORD_PATTERN = re.compile(r"[^\W\d_][\w'-]*", re.UNICODE)
CLOSING_PUNCTUATION = "\"'\u2019\u201d\u00bb)]}"
ABBREVIATIONS = {
    "approx.", "dept.", "dr.", "e.g.", "etc.", "fig.", "i.e.", "jr.",
    "mr.", "mrs.", "ms.", "no.", "prof.", "sr.", "vs.",
}
DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:,\s+\d{4})?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Analysis:
    """The information extracted from a document."""

    title: str
    key_points: list[str]
    keywords: list[str]
    dates: list[str]


class PDFExtractionError(ValueError):
    """Raised when a PDF cannot provide readable text."""


class WordExtractionError(ValueError):
    """Raised when a Word document cannot provide readable text."""


class WebsiteExtractionError(ValueError):
    """Raised when a website does not contain readable text."""


class _HTMLTextParser:
    """Extract readable text while ignoring non-content HTML elements."""

    def __init__(self) -> None:
        from html.parser import HTMLParser

        class Parser(HTMLParser):
            def __init__(self, owner: "_HTMLTextParser") -> None:
                super().__init__(convert_charrefs=True)
                self.owner = owner
                self.ignored_depth = 0
                self.block_depth = 0
                self.block_parts: list[str] = []
                self.block_tag = ""

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                structural_name = next(
                    (value or "" for name, value in attrs if name in {"id", "class"}),
                    "",
                ).lower()
                ignored_names = (
                    "nav", "menu", "sidebar", "footer", "header", "toolbar",
                    "reference", "citation", "infobox", "toc", "metadata",
                )
                if (
                    tag in {"head", "script", "style", "noscript", "template", "svg", "table", "sup"}
                    or any(name in structural_name for name in ignored_names)
                ):
                    self.ignored_depth += 1
                elif not self.ignored_depth and tag in {"p", "h1", "h2", "h3"}:
                    self.block_depth += 1
                    if self.block_depth == 1:
                        self.block_parts = []
                        self.block_tag = tag

            def handle_endtag(self, tag: str) -> None:
                if tag in {"head", "script", "style", "noscript", "template", "svg", "table", "sup"} and self.ignored_depth:
                    self.ignored_depth -= 1
                elif not self.ignored_depth and tag in {"p", "h1", "h2", "h3"} and self.block_depth:
                    self.block_depth -= 1
                    if self.block_depth == 0:
                        block = re.sub(r"\s+", " ", "".join(self.block_parts)).strip()
                        if len(block.split()) >= (1 if self.block_tag in {"h1", "h2", "h3"} else 3):
                            self.owner.parts.append(block)
                        self.block_parts = []
                        self.block_tag = ""

            def handle_data(self, data: str) -> None:
                if not self.ignored_depth:
                    if self.block_depth:
                        self.block_parts.append(data)

        self.parts: list[str] = []
        self.parser = Parser(self)

    def feed(self, content: str) -> str:
        self.parser.feed(content)
        return html.unescape("\n".join(self.parts)).strip()


def _is_website(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def fetch_website(url: str, timeout: float = 15.0) -> str:
    """Fetch and extract readable text from an HTTP(S) website."""
    if not _is_website(url):
        raise ValueError("website URL must start with http:// or https://")

    request = Request(url, headers={"User-Agent": "SummarizeIT/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            content = response.read().decode(content_type, errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise WebsiteExtractionError(OFFLINE_FALLBACK) from error

    text = _HTMLTextParser().feed(content)
    if not text:
        raise WebsiteExtractionError("The website does not contain readable text.")
    return text


def _validate_positive_limit(value: int, argument_name: str) -> None:
    """Reject summary limits that cannot select any sentences."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{argument_name} must be an integer")
    if value < 1:
        raise ValueError(f"{argument_name} must be at least 1")


def _is_sentence_boundary(text: str, index: int) -> bool:
    """Return whether punctuation at index ends a sentence."""
    punctuation = text[index]
    if punctuation != ".":
        return True

    start = index
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    token = text[start : index + 1]
    previous = text[index - 1] if index else ""
    following = text[index + 1] if index + 1 < len(text) else ""

    if previous.isdigit() and following.isdigit():
        return False
    if token.lower() in ABBREVIATIONS:
        return False
    if len(token) == 2 and token[0].isupper():
        return False
    if token.count(".") > 1 and token[-2:-1].isalpha():
        return False
    return True


def split_sentences(text: str) -> list[str]:
    """Split text into readable, non-empty sentence-like units."""
    sentences = []
    start = 0
    for index, character in enumerate(text):
        if character == "\n" or (
            character in ".!?" and _is_sentence_boundary(text, index)
        ):
            following = index + 1
            while following < len(text) and text[following] in CLOSING_PUNCTUATION:
                following += 1
            if following < len(text) and not text[following].isspace():
                continue
            sentence = text[start:following].strip()
            if sentence:
                sentences.append(sentence)
            start = following

    trailing = text[start:].strip()
    if trailing:
        sentences.append(trailing)
    return sentences


def extract_analysis(text: str, max_points: int = 3) -> Analysis:
    """Extract a title, key points, keywords, and dates from text."""
    _validate_positive_limit(max_points, "max_points")
    sentences = split_sentences(text)
    title = sentences[0] if sentences else "Untitled document"

    words = [word.lower() for word in WORD_PATTERN.findall(text)]
    frequencies = Counter(word for word in words if word not in STOP_WORDS)
    keywords = [word for word, _ in frequencies.most_common(5)]

    # Build per-sentence word sets once so IDF can be computed without rescanning
    # every sentence for each word.
    sentence_word_sets = [
        {w.lower() for w in WORD_PATTERN.findall(s) if w.lower() not in STOP_WORDS}
        for s in sentences
    ]
    sentence_frequencies = Counter(
        word for word_set in sentence_word_sets for word in word_set
    )
    n = len(sentences)

    scored_sentences = []
    for index, (sentence, word_set) in enumerate(zip(sentences, sentence_word_sets)):
        score = 0.0
        for word in word_set:
            # TF: global frequency acts as a proxy for within-document importance.
            tf = frequencies[word]
            # IDF: down-weight words that appear in many sentences (not distinctive).
            doc_count = sentence_frequencies[word]
            idf = math.log((n + 1) / (doc_count + 1)) + 1.0
            score += tf * idf
        meaningful_count = len(word_set)
        if meaningful_count:
            # Prefer focused sentences over long sentences padded with generic words.
            score = score / math.sqrt(meaningful_count)
            # Earlier sentences usually establish context, but content remains dominant.
            score += 0.15 * (n - index) / max(n, 1)
        scored_sentences.append((score, -index, sentence, word_set))

    candidates = [item for item in scored_sentences if item[0] > 0]
    selected: list[tuple[float, int, str, set[str]]] = []
    while candidates and len(selected) < max_points:
        best = max(
            candidates,
            key=lambda item: item[0]
            - max(
                (
                    len(item[3] & chosen[3]) / max(len(item[3] | chosen[3]), 1)
                    for chosen in selected
                ),
                default=0.0,
            ),
        )
        selected.append(best)
        candidates.remove(best)

    key_points = [
        sentence
        for _, _, sentence, _ in sorted(selected, key=lambda item: -item[1])
    ]
    dates = list(dict.fromkeys(DATE_PATTERN.findall(text)))

    return Analysis(title=title, key_points=key_points, keywords=keywords, dates=dates)


def format_report(analysis: Analysis, summary: str) -> str:
    """Render analysis results as a human-readable report."""
    lines = [
        f"Title: {analysis.title}",
        "",
        "Summary:",
        summary or "No summary could be generated because the document is empty.",
        "",
        "Key information:",
    ]
    lines.extend(f"- {point}" for point in analysis.key_points)
    lines.extend(["", f"Keywords: {', '.join(analysis.keywords) or 'None'}"])
    lines.append(f"Dates: {', '.join(analysis.dates) or 'None'}")
    return "\n".join(lines)


def read_document(input_path: Path) -> str:
    """Read a supported text, PDF, or DOCX document."""
    if input_path.suffix.lower() == ".doc":
        raise WordExtractionError("only .docx Word files are supported")

    if input_path.suffix.lower() == ".docx":
        try:
            from docx import Document
        except ImportError as error:
            raise WordExtractionError(
                "Word support requires the python-docx package; install the project dependencies."
            ) from error

        try:
            document = Document(str(input_path))
            text = "\n".join(
                paragraph.text
                for paragraph in document.paragraphs
                if paragraph.text.strip()
            ).strip()
        except Exception as error:
            raise WordExtractionError(f"could not read Word document: {error}") from error
        if not text:
            raise WordExtractionError("The Word document does not contain readable text.")
        return text

    if input_path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError as error:
            raise PDFExtractionError(
                "PDF support requires the pypdf package; install the project dependencies."
            ) from error

        try:
            reader = PdfReader(str(input_path))
            if reader.is_encrypted and not reader.decrypt(""):
                raise PDFExtractionError("The PDF is encrypted and requires a password.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except PDFExtractionError:
            raise
        except PdfReadError as error:
            raise PDFExtractionError(f"could not read PDF: {error}") from error
        if not text:
            raise PDFExtractionError("The PDF does not contain extractable text.")
        return text

    return input_path.read_text(encoding="utf-8")


def summarize_file(input_path: Path, max_sentences: int = 3) -> str:
    """Read and summarize a supported text, PDF, or DOCX document."""
    _validate_positive_limit(max_sentences, "max_sentences")
    text = read_document(input_path)
    analysis = extract_analysis(text, max_points=max_sentences)
    summary = " ".join(analysis.key_points)
    return format_report(analysis, summary)


def summarize_website(url: str, max_sentences: int = 3) -> str:
    """Fetch and summarize a website, returning the offline fallback when unavailable."""
    _validate_positive_limit(max_sentences, "max_sentences")
    try:
        text = fetch_website(url)
    except WebsiteExtractionError as error:
        if str(error) == OFFLINE_FALLBACK:
            return OFFLINE_FALLBACK
        raise
    analysis = extract_analysis(text, max_points=max_sentences)
    return format_report(analysis, " ".join(analysis.key_points))


def summarize_source(source: str | Path, max_sentences: int = 3) -> str:
    """Summarize either a local document path or an HTTP(S) website."""
    source_text = str(source)
    if _is_website(source_text):
        return summarize_website(source_text, max_sentences=max_sentences)
    return summarize_file(Path(source_text), max_sentences=max_sentences)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize a text/PDF file or an HTTP(S) website.",
        epilog=(
            "Windows examples:\n"
            "  PowerShell: py mini_agent.py document.pdf\n"
            "  Command Prompt: py mini_agent.py document.txt --output report.txt\n"
            "Use quotes around paths that contain spaces."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    parser.add_argument("input", help="path to a UTF-8 text/PDF file or an HTTP(S) website")
    parser.add_argument(
        "-o", "--output", type=Path, help="write the report to a file instead of stdout"
    )
    parser.add_argument(
        "-n",
        "--sentences",
        type=int,
        default=3,
        help="maximum number of sentences in the summary (default: 3)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.sentences < 1:
        parser.error("--sentences must be at least 1")

    try:
        report = summarize_source(args.input, max_sentences=args.sentences)
    except FileNotFoundError:
        parser.error(f"input file not found: {args.input}")
    except UnicodeDecodeError:
        parser.error(f"input file is not valid UTF-8: {args.input}")
    except PDFExtractionError as error:
        parser.error(str(error))
    except WordExtractionError as error:
        parser.error(str(error))
    except WebsiteExtractionError as error:
        parser.error(str(error))
    except OSError as error:
        parser.error(str(error))

    if args.output:
        try:
            args.output.write_text(report + "\n", encoding="utf-8")
        except OSError as error:
            parser.error(f"could not write output file: {error}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())