"""Modern PySide6 desktop interface for the offline text summarizer."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mini_agent import (
    OFFLINE_FALLBACK,
    PDFExtractionError,
    WordExtractionError,
    extract_analysis,
    format_report,
    read_document,
    summarize_website,
)


class DocumentEditor(QTextEdit):
    """Text editor that accepts dropped UTF-8 files with visual feedback."""

    file_dropped = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            self.setProperty("dragOver", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)
        urls = event.mimeData().urls()
        if urls:
            self.file_dropped.emit(urls[0].toLocalFile())
            event.acceptProposedAction()
        else:
            event.ignore()


class GlassPanel(QFrame):
    """A reusable rounded panel used for the editor and report surfaces."""

    def __init__(self, object_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)


class SummarizeWindow(QMainWindow):
    """Premium dark desktop shell around the summarizer's existing core."""

    def __init__(self) -> None:
        super().__init__()
        self.current_path: Path | None = None
        self.report_text = ""
        self.setWindowTitle("SummarizeIT")
        self.setMinimumSize(960, 640)
        self.resize(1240, 800)
        self._build_ui()
        self._bind_shortcuts()
        self._animate_intro()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(36, 30, 36, 24)
        layout.setSpacing(22)

        header = QHBoxLayout()
        header.setSpacing(14)
        brand = QLabel("S")
        brand.setObjectName("BrandMark")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setFixedSize(46, 46)
        brand_glow = QGraphicsDropShadowEffect(brand)
        brand_glow.setColor(QColor("#7657ff"))
        brand_glow.setBlurRadius(24)
        brand_glow.setOffset(0, 0)
        brand.setGraphicsEffect(brand_glow)
        header.addWidget(brand)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        title = QLabel("SummarizeIT")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Clearer thinking, in a few seconds.")
        subtitle.setObjectName("AppSubtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack)
        header.addStretch()

        self.file_label = QLabel("No document loaded")
        self.file_label.setObjectName("FileLabel")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.file_label)
        layout.addLayout(header)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        self.open_button = QPushButton("Open document")
        self.open_button.setObjectName("SecondaryButton")
        self.open_button.setToolTip("Open a text or PDF document (Ctrl+O)")
        self.open_button.clicked.connect(self.open_file)
        actions.addWidget(self.open_button)

        self.paste_button = QPushButton("Paste text")
        self.paste_button.setObjectName("SecondaryButton")
        self.paste_button.setToolTip("Paste text from the clipboard (Ctrl+Shift+V)")
        self.paste_button.clicked.connect(self.paste_text)
        actions.addWidget(self.paste_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("SecondaryButton")
        self.clear_button.setToolTip("Clear document and report (Ctrl+Backspace)")
        self.clear_button.clicked.connect(self.clear_document)
        actions.addWidget(self.clear_button)

        self.copy_button = QPushButton("Copy report")
        self.copy_button.setObjectName("SecondaryButton")
        self.copy_button.setToolTip("Copy the generated report to clipboard (Ctrl+Shift+C)")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_report)
        actions.addWidget(self.copy_button)

        self.save_button = QPushButton("Save report")
        self.save_button.setObjectName("SecondaryButton")
        self.save_button.setToolTip("Save the generated report to a file (Ctrl+S)")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_report)
        actions.addWidget(self.save_button)
        actions.addStretch()

        length_label = QLabel("Summary length")
        length_label.setObjectName("ControlLabel")
        actions.addWidget(length_label)
        self.sentence_limit = QSpinBox()
        self.sentence_limit.setRange(1, 20)
        self.sentence_limit.setValue(3)
        self.sentence_limit.setSuffix(" sentences")
        self.sentence_limit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.sentence_limit.setMinimumWidth(136)
        self.sentence_limit.setReadOnly(False)
        self.sentence_limit.setToolTip("Maximum number of sentences in the summary")
        actions.addWidget(self.sentence_limit)
        layout.addLayout(actions)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("WorkspaceSplitter")
        splitter.setChildrenCollapsible(False)

        input_panel, self.input_text, self.input_stats_label = self._make_editor_panel(
            "YOUR DOCUMENT",
            "Drop a .txt, .md, .pdf, or .docx file, website url here or start typing...",
            editable=True,
        )
        output_panel, self.output_text, self.output_stats_label = self._make_editor_panel(
            "YOUR REPORT", "Your generated report will appear here.", editable=False
        )
        self.input_text.file_dropped.connect(self.load_path)
        self.input_text.textChanged.connect(self._on_input_changed)
        splitter.addWidget(input_panel)
        splitter.addWidget(output_panel)
        splitter.setSizes([1, 1])
        layout.addWidget(splitter, stretch=1)

        footer = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setObjectName("ProgressBar")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(120)
        self.progress.hide()
        footer.addWidget(self.progress)
        self.status = QLabel("Ready when you are.")
        self.status.setObjectName("StatusLabel")
        footer.addWidget(self.status)
        footer.addStretch()
        hint = QLabel(
            "Ctrl+O open  ·  Ctrl+Shift+V paste  ·  Ctrl+Enter summarize  ·  "
            "Ctrl+Shift+C copy  ·  Ctrl+S save"
        )
        hint.setObjectName("HintLabel")
        footer.addWidget(hint)
        layout.addLayout(footer)

    def _make_editor_panel(
        self, label: str, placeholder: str, editable: bool
    ) -> tuple[GlassPanel, DocumentEditor, QLabel]:
        panel = GlassPanel("GlassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 18)
        panel_layout.setSpacing(10)
        heading = QHBoxLayout()
        heading_label = QLabel(label)
        heading_label.setObjectName("PanelLabel")
        heading.addWidget(heading_label)
        heading.addStretch()
        stats_label = QLabel("0 words" if editable else "PREVIEW")
        stats_label.setObjectName("PanelState")
        heading.addWidget(stats_label)
        panel_layout.addLayout(heading)

        editor = DocumentEditor()
        editor.setObjectName("Editor" if editable else "ReportEditor")
        editor.setPlaceholderText(placeholder)
        editor.setReadOnly(not editable)
        editor.setAcceptRichText(False)
        editor.setUndoRedoEnabled(editable)
        panel_layout.addWidget(editor, stretch=1)
        return panel, editor, stats_label

    def _bind_shortcuts(self) -> None:
        open_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        open_shortcut.activated.connect(self.open_file)
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_report)
        copy_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        copy_shortcut.activated.connect(self.copy_report)
        paste_shortcut = QShortcut(QKeySequence("Ctrl+Shift+V"), self)
        paste_shortcut.activated.connect(self.paste_text)
        summarize_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        summarize_shortcut.activated.connect(self.summarize)

        clear_action = QAction(self)
        clear_action.setShortcut(QKeySequence("Ctrl+Backspace"))
        clear_action.triggered.connect(self.clear_document)
        self.addAction(clear_action)

    def _animate_intro(self) -> None:
        central_widget = self.centralWidget()
        if central_widget is None:
            return

        effect = QGraphicsOpacityEffect(central_widget)
        effect.setOpacity(0.0)
        central_widget.setGraphicsEffect(effect)
        self.intro_animation = QPropertyAnimation(effect, b"opacity", self)
        self.intro_animation.setDuration(420)
        self.intro_animation.setStartValue(0.0)
        self.intro_animation.setEndValue(1.0)
        self.intro_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.intro_animation.start()

    def _on_input_changed(self) -> None:
        text = self.input_text.toPlainText()
        central_widget = self.centralWidget()
        if central_widget is not None:
            central_widget.setProperty("urlMode", text.strip().startswith(("http://", "https://")))
            widget_style = central_widget.style()
            widget_style.unpolish(central_widget)
            widget_style.polish(central_widget)
        if self.current_path and not self.file_label.text().endswith(" (edited)"):
            self.file_label.setText(f"{self.current_path.name} (edited)")
        self._update_input_stats(text)

    def _update_input_stats(self, text: str) -> None:
        words = len(text.split())
        if words == 0:
            self.input_stats_label.setText("0 words")
            return
        reading_time = max(1, round(words / 200))
        time_text = f"~{reading_time} min read" if reading_time > 1 else "< 1 min read"
        self.input_stats_label.setText(f"{words:,} words  ·  {time_text}")

    def load_path(self, raw_path: str) -> None:
        path = Path(raw_path)
        if not path.is_file():
            return
        try:
            text = read_document(path)
        except UnicodeDecodeError:
            self._show_error("Open failed", "The selected file is not valid UTF-8.")
            return
        except PDFExtractionError as error:
            self._show_error("Open failed", str(error))
            return
        except WordExtractionError as error:
            self._show_error("Open failed", str(error))
            return
        except OSError as error:
            self._show_error("Open failed", str(error))
            return

        self.current_path = path
        self.input_text.blockSignals(True)
        self.input_text.setPlainText(text)
        self.input_text.blockSignals(False)
        self._update_input_stats(text)
        self.file_label.setText(path.name)
        self.status.setText(f"Loaded {path.name}")
        self.output_text.clear()
        self.report_text = ""
        self.output_stats_label.setText("PREVIEW")
        self.save_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        QTimer.singleShot(0, self.summarize)

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open document",
            "",
            "Supported documents (*.txt *.md *.markdown *.rst *.log *.pdf *.docx);;Text documents (*.txt *.md *.markdown *.rst *.log);;PDF files (*.pdf);;Word documents (*.docx);;All files (*)",
        )
        if path:
            self.load_path(path)

    def clear_document(self) -> None:
        self.input_text.blockSignals(True)
        self.input_text.clear()
        self.input_text.blockSignals(False)
        self.output_text.clear()
        self.current_path = None
        self.report_text = ""
        self.file_label.setText("No document loaded")
        self.save_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.input_stats_label.setText("0 words")
        self.output_stats_label.setText("PREVIEW")
        self.status.setText("Workspace cleared.")

    def paste_text(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        text = clipboard.text()
        if not text.strip():
            self.status.setText("Clipboard does not contain text.")
            return
        self.input_text.setPlainText(text)
        self.current_path = None
        self.file_label.setText("Pasted text")
        self.output_text.clear()
        self.report_text = ""
        self.output_stats_label.setText("PREVIEW")
        self.save_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.status.setText("Pasted text from clipboard.")

    def copy_report(self) -> None:
        if not self.report_text:
            return
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.report_text)
            self.status.setText("Report copied to clipboard.")
            self.copy_button.setText("Copied!")
            QTimer.singleShot(1800, lambda: self.copy_button.setText("Copy report"))

    def summarize(self) -> None:
        text = self.input_text.toPlainText().strip()
        if not text:
            self._show_error("Nothing to summarize", "Add or open a document first.")
            return

        self._set_busy(True)
        QTimer.singleShot(80, lambda: self._finish_summary(text))

    def _finish_summary(self, text: str) -> None:
        try:
            if text.startswith(("http://", "https://")):
                self.report_text = summarize_website(
                    text, max_sentences=self.sentence_limit.value()
                )
                self.output_text.setPlainText(self.report_text)
                self.save_button.setEnabled(True)
                self.copy_button.setEnabled(True)
                self.output_stats_label.setText(
                    "Connection unavailable"
                    if self.report_text == OFFLINE_FALLBACK
                    else "Website summary"
                )
                self.status.setText(
                    "Internet connection unavailable."
                    if self.report_text == OFFLINE_FALLBACK
                    else "Website summary ready."
                )
                return
            analysis = extract_analysis(text, max_points=self.sentence_limit.value())
            self.report_text = format_report(analysis, " ".join(analysis.key_points))
            self.output_text.setPlainText(self.report_text)
            self.save_button.setEnabled(True)
            self.copy_button.setEnabled(True)
            self.status.setText("Summary ready.")
            input_words = len(text.split())
            report_words = len(" ".join(analysis.key_points).split())
            if input_words > 0 and report_words > 0:
                reduction = max(0, round((1.0 - (report_words / input_words)) * 100))
                self.output_stats_label.setText(f"{report_words} summary words  ·  -{reduction}%")
            else:
                self.output_stats_label.setText(f"{report_words} summary words")
        except Exception as error:
            self.report_text = ""
            self.output_text.clear()
            self.save_button.setEnabled(False)
            self.copy_button.setEnabled(False)
            self.output_stats_label.setText("PREVIEW")
            self.status.setText("Summary failed.")
            self._show_error("Summary failed", str(error))
        finally:
            self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.open_button.setEnabled(not busy)
        self.paste_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        if busy:
            self.save_button.setEnabled(False)
            self.copy_button.setEnabled(False)
        else:
            has_report = bool(self.report_text)
            self.save_button.setEnabled(has_report)
            self.copy_button.setEnabled(has_report)
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)
            self.status.setText("Reading the signal...")
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)

    def save_report(self) -> None:
        if not self.report_text:
            return
        initial_name = (
            f"{self.current_path.stem} report.txt"
            if self.current_path
            else "summary report.txt"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save report",
            initial_name,
            "Text files (*.txt);;Markdown files (*.md);;All files (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self.report_text + "\n", encoding="utf-8")
        except OSError as error:
            self._show_error("Save failed", str(error))
            return
        self.status.setText(f"Saved {Path(path).name}")

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)


def dark_palette() -> QPalette:
    """Return a consistent dark palette for platforms without a dark default."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f0f6fc"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#111820"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#161f2a"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#f0f6fc"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f0f6fc"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#182331"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f0f6fc"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#7c5cff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    return palette


def stylesheet() -> str:
    return """
    * { font-family: "Cambria Math", "Cambria", serif; color: #f0f6fc; }
    QMainWindow, #Root { background: #0d1117; }
    QLabel#AppTitle { font-size: 24px; font-weight: 700; color: #f0f6fc; }
    QLabel#AppSubtitle, QLabel#FileLabel, QLabel#HintLabel,
    QLabel#StatusLabel, QLabel#ControlLabel { color: #8b98a9; }
    QLabel#AppSubtitle { font-size: 12px; }
    QLabel#FileLabel { font-size: 12px; padding: 7px 12px; border: 1px solid #273446; border-radius: 12px; }
    QLabel#BrandMark { color: #ffffff; font-size: 22px; font-weight: 800; border-radius: 14px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7657ff, stop:1 #bd5cff); }
    QLabel#PanelLabel { color: #b9c4d2; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
    QLabel#PanelState { color: #8b98a9; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 6px; background: #16202c; border: 1px solid #243142; }
    QFrame#GlassPanel { background: rgba(20, 30, 42, 225); border: 1px solid #263446; border-radius: 18px; }
    QSplitter::handle { background: transparent; width: 14px; }
    QTextEdit#Editor, QTextEdit#ReportEditor { background: rgba(21, 30, 40, 235); border: 1px solid #253344; border-radius: 12px; padding: 14px; color: #e6edf3; selection-background-color: #5b43c8; font-size: 14px; }
    QTextEdit#Editor:focus, QTextEdit#ReportEditor:focus { border: 1px solid #7657ff; }
    QTextEdit#Editor[dragOver="true"] { border: 2px dashed #987fff; background: rgba(30, 44, 66, 245); }
    QTextEdit#ReportEditor { color: #c8d1dc; }
    QPushButton { min-height: 34px; padding: 0 16px; border-radius: 10px; font-weight: 600; border: 1px solid #718096; }
    QPushButton#SecondaryButton { background: #182331; border: 1px solid #718096; color: #f0f6fc; }
    QPushButton#SecondaryButton:hover { background: #2b3645; border-color: #cbd5e1; color: #ffffff; }
    QPushButton#SecondaryButton:pressed { background: #121a24; }
    QPushButton#PrimaryButton { background: #161b22; border: 1px solid #cbd5e1; color: #ffffff; padding: 0 20px; }
    QPushButton#PrimaryButton:hover { background: #7657ff; border-color: #b7aaff; color: #ffffff; }
    QPushButton#PrimaryButton:pressed { background: #0d1117; }
    QPushButton:disabled { color: #647184; background: #141b24; border-color: #202b38; }
    QSpinBox { min-height: 32px; padding: 0 14px; border: 1px solid #2a3a4f; border-radius: 9px; background: #151e28; color: #f0f6fc; }
    QSpinBox:hover { border-color: #536b8d; }
    QSpinBox:focus { border-color: #7657ff; }
    QProgressBar#ProgressBar { border: 0; border-radius: 3px; background: #202b38; max-height: 6px; }
    QProgressBar#ProgressBar::chunk { border-radius: 3px; background: #7657ff; }
    #Root[urlMode="true"] { background: #050608; }
    #Root[urlMode="true"] QFrame#GlassPanel { background: #11151b; border-color: #8994a3; }
    #Root[urlMode="true"] QTextEdit#Editor, #Root[urlMode="true"] QTextEdit#ReportEditor { background: #080a0d; border-color: #8994a3; }
    #Root[urlMode="true"] QPushButton { background: #11151b; border-color: #cbd5e1; }
    #Root[urlMode="true"] QPushButton#PrimaryButton:hover { background: #7657ff; border-color: #b7aaff; color: #ffffff; }
    """


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(stylesheet())
    window = SummarizeWindow()
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
