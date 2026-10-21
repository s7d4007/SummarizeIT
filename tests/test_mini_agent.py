import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from mini_agent import (
    extract_analysis,
    format_report,
    main,
    split_sentences,
    summarize_file,
)


class MiniAgentTests(unittest.TestCase):
    def test_extracts_key_information_and_ranks_sentences(self):
        text = (
            "Project Aurora launched on March 5, 2026. "
            "The team built an offline search tool for researchers. "
            "The search tool indexes reports and returns results quickly."
        )

        analysis = extract_analysis(text, max_points=2)

        self.assertEqual(analysis.title, "Project Aurora launched on March 5, 2026.")
        self.assertEqual(analysis.dates, ["March 5, 2026"])
        self.assertIn("search", analysis.keywords)
        self.assertEqual(len(analysis.key_points), 2)
        self.assertIn("search tool", " ".join(analysis.key_points))

    def test_empty_document_has_safe_report(self):
        analysis = extract_analysis("")

        self.assertEqual(analysis.title, "Untitled document")
        self.assertEqual(analysis.key_points, [])
        self.assertIn("No summary could be generated", summarize_file_from_text(""))

    def test_format_report_renders_analysis_without_gui_dependencies(self):
        analysis = extract_analysis(
            "Release begins on March 5, 2026. The team ships the offline report tool."
        )

        report = format_report(analysis, "The team ships the offline report tool.")

        self.assertIn("Title: Release begins on March 5, 2026.", report)
        self.assertIn("Summary:\nThe team ships the offline report tool.", report)
        self.assertIn("Key information:", report)
        self.assertIn("- The team ships the offline report tool.", report)
        self.assertIn("Keywords:", report)
        self.assertIn("Dates: March 5, 2026", report)

    def test_mixed_punctuation_unicode_and_non_english_text_are_preserved(self):
        text = "¡Hola! Привет мир? Café déjà vu."

        sentences = split_sentences(text)
        analysis = extract_analysis(text)
        report = format_report(analysis, " ".join(analysis.key_points))

        self.assertEqual(sentences, ["¡Hola!", "Привет мир?", "Café déjà vu."])
        self.assertEqual(analysis.title, "¡Hola!")
        self.assertIn("¡Hola!", report)
        self.assertIn("Café déjà vu.", report)

    def test_large_document_returns_requested_number_of_key_points(self):
        text = " ".join(
            f"Record {index} contains the searchable project update." for index in range(1500)
        )

        analysis = extract_analysis(text, max_points=5)

        self.assertEqual(len(analysis.key_points), 5)
        self.assertTrue(all(point.endswith(".") for point in analysis.key_points))

    def test_split_sentences_handles_newlines_and_empty_lines(self):
        text = "\nFirst point.\n\nSecond point!\nThird point?"

        self.assertEqual(
            split_sentences(text),
            ["First point.", "Second point!", "Third point?"],
        )

    def test_split_sentences_preserves_abbreviations_and_decimal_numbers(self):
        text = "Dr. Smith reviewed version 1.2. The result was good. See e.g. the report."

        self.assertEqual(
            split_sentences(text),
            [
                "Dr. Smith reviewed version 1.2.",
                "The result was good.",
                "See e.g. the report.",
            ],
        )

    def test_extract_analysis_deduplicates_dates_in_source_order(self):
        text = (
            "The review starts on March 5, 2026. "
            "The review ends on 2026-03-06. "
            "The review date remains March 5, 2026."
        )

        analysis = extract_analysis(text)

        self.assertEqual(
            analysis.dates,
            ["March 5, 2026", "2026-03-06"],
        )

    def test_stop_word_only_document_has_no_keywords(self):
        analysis = extract_analysis("The and of in.")

        self.assertEqual(analysis.keywords, [])
        self.assertEqual(analysis.key_points, [])

    def test_zero_score_sentences_are_not_selected_with_meaningful_sentences(self):
        analysis = extract_analysis("The and of in. Search results are ready.", max_points=3)

        self.assertEqual(analysis.key_points, ["Search results are ready."])

    def test_max_points_limits_key_points_without_reordering_them(self):
        text = "Alpha alpha alpha. Beta beta. Gamma."

        analysis = extract_analysis(text, max_points=2)

        self.assertEqual(analysis.key_points, ["Alpha alpha alpha.", "Beta beta."])

    def test_extract_analysis_rejects_invalid_max_points(self):
        for max_points in (0, -1):
            with self.subTest(max_points=max_points):
                with self.assertRaisesRegex(ValueError, "max_points must be at least 1"):
                    extract_analysis("A sentence.", max_points=max_points)

        with self.assertRaisesRegex(TypeError, "max_points must be an integer"):
            extract_analysis("A sentence.", max_points=1.5)

    def test_summarize_file_rejects_invalid_max_sentences_before_reading(self):
        missing_path = Path("missing-document.txt")

        for max_sentences in (0, -1):
            with self.subTest(max_sentences=max_sentences):
                with self.assertRaisesRegex(
                    ValueError, "max_sentences must be at least 1"
                ):
                    summarize_file(missing_path, max_sentences=max_sentences)

        with self.assertRaisesRegex(TypeError, "max_sentences must be an integer"):
            summarize_file(missing_path, max_sentences=1.5)

    def test_parser_rejects_non_positive_sentence_limit(self):
        for sentence_limit in ("0", "-1"):
            with self.subTest(sentence_limit=sentence_limit):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        main(["document.txt", "--sentences", sentence_limit])

    def test_main_reports_missing_input_path(self):
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit):
                main(["missing-document.txt"])

        self.assertIn("input file not found", stderr.getvalue())

    def test_main_reports_invalid_utf8_input(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "invalid.txt"
            input_path.write_bytes(b"valid text\xff")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit):
                    main([str(input_path)])

        self.assertIn("not valid UTF-8", stderr.getvalue())

    def test_main_reports_missing_output_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "document.txt"
            output_path = Path(directory) / "missing" / "report.txt"
            input_path.write_text("A useful project update.", encoding="utf-8")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit):
                    main([str(input_path), "--output", str(output_path)])

        self.assertIn("No such file or directory", stderr.getvalue())

    def test_main_writes_utf8_report_to_output_path(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "document.txt"
            output_path = Path(directory) / "report.txt"
            input_path.write_text("Résumé: café is ready.", encoding="utf-8")

            self.assertEqual(
                main([str(input_path), "--output", str(output_path)]),
                0,
            )

            report = output_path.read_text(encoding="utf-8")

        self.assertIn("Title: Résumé: café is ready.", report)
        self.assertTrue(report.endswith("\n"))


def summarize_file_from_text(text: str) -> str:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "document.txt"
        path.write_text(text, encoding="utf-8")
        return summarize_file(path)


if __name__ == "__main__":
    unittest.main()
