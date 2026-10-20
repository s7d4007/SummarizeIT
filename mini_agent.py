"""A small dependency-free text summarization agent."""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "will", "with", "you", "your",
}
WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]*")
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
        scored_sentences.append((score, -index, sentence))

    ranked = sorted(
        (item for item in scored_sentences if item[0] > 0),
        reverse=True,
    )[:max_points]
    key_points = [sentence for _, _, sentence in sorted(ranked, key=lambda item: -item[1])]
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


def summarize_file(input_path: Path, max_sentences: int = 3) -> str:
    """Read and summarize a UTF-8 text file."""
    _validate_positive_limit(max_sentences, "max_sentences")
    text = input_path.read_text(encoding="utf-8")
    analysis = extract_analysis(text, max_points=max_sentences)
    summary = " ".join(analysis.key_points)
    return format_report(analysis, summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read a UTF-8 text file, extract key information, and produce a summary.",
        epilog=(
            "Windows examples:\n"
            "  PowerShell: py mini_agent.py document.txt\n"
            "  Command Prompt: py mini_agent.py document.txt --output report.txt\n"
            "Use quotes around paths that contain spaces."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="path to a UTF-8 text file")
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
        report = summarize_file(args.input, max_sentences=args.sentences)
        if args.output:
            args.output.write_text(report + "\n", encoding="utf-8")
        else:
            print(report)
    except FileNotFoundError:
        parser.error(f"input file not found: {args.input}")
    except UnicodeDecodeError:
        parser.error(f"input file is not valid UTF-8: {args.input}")
    except OSError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())