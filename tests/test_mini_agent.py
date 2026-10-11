import tempfile
import unittest
from pathlib import Path

from mini_agent import extract_analysis, summarize_file


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


def summarize_file_from_text(text: str) -> str:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "document.txt"
        path.write_text(text, encoding="utf-8")
        return summarize_file(path)


if __name__ == "__main__":
    unittest.main()
