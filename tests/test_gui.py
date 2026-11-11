import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from PySide6.QtWidgets import QApplication, QPushButton
    from PySide6.QtTest import QTest
    from gui import SummarizeWindow
except ImportError:  # pragma: no cover - exercised when GUI extras are absent
    QApplication = None
    QPushButton = None
    QTest = None
    SummarizeWindow = None


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class SummarizeWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = SummarizeWindow()
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()

    def wait_for_summary(self):
        QTest.qWait(140)
        self.application.processEvents()

    def test_initial_state_has_no_visible_summarize_button(self):
        button_texts = {
            button.text() for button in self.window.findChildren(QPushButton)
        }

        self.assertNotIn("Summarize", button_texts)
        self.assertFalse(self.window.save_button.isEnabled())
        self.assertFalse(self.window.copy_button.isEnabled())
        self.assertEqual(self.window.status.text(), "Ready when you are.")

    def test_typed_text_can_be_summarized_with_keyboard_action(self):
        self.window.input_text.setPlainText(
            "The project ships an offline report tool. "
            "The report tool helps readers find useful details."
        )

        self.window.summarize()
        self.wait_for_summary()

        self.assertIn("Summary:", self.window.report_text)
        self.assertIn("offline report tool", self.window.report_text)
        self.assertEqual(self.window.status.text(), "Summary ready.")
        self.assertTrue(self.window.save_button.isEnabled())
        self.assertTrue(self.window.copy_button.isEnabled())

    def test_opening_docx_path_loads_and_summarizes_automatically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meeting.docx"
            path.write_bytes(b"mock docx")

            with mock.patch(
                "gui.read_document",
                return_value="The meeting produced three decisions.",
            ):
                self.window.load_path(str(path))
                self.wait_for_summary()

        self.assertEqual(self.window.file_label.text(), "meeting.docx")
        self.assertIn("three decisions", self.window.report_text)
        self.assertEqual(self.window.status.text(), "Summary ready.")

    def test_clear_resets_document_and_report_state(self):
        self.window.input_text.setPlainText("A useful project update.")
        self.window.summarize()
        self.wait_for_summary()

        self.window.clear_document()

        self.assertEqual(self.window.input_text.toPlainText(), "")
        self.assertEqual(self.window.output_text.toPlainText(), "")
        self.assertEqual(self.window.report_text, "")
        self.assertEqual(self.window.file_label.text(), "No document loaded")
        self.assertFalse(self.window.save_button.isEnabled())
        self.assertFalse(self.window.copy_button.isEnabled())

    def test_save_report_uses_selected_output_path(self):
        self.window.input_text.setPlainText("A useful project update.")
        self.window.summarize()
        self.wait_for_summary()

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "report.txt"
            with mock.patch(
                "gui.QFileDialog.getSaveFileName",
                return_value=(str(output_path), "Text files (*.txt)"),
            ):
                self.window.save_report()

            self.assertEqual(output_path.read_text(encoding="utf-8"), self.window.report_text + "\n")
            self.assertEqual(self.window.status.text(), "Saved report.txt")


if __name__ == "__main__":
    unittest.main()