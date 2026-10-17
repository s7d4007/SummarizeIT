"""Desktop interface for the offline text summarizer."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from mini_agent import extract_analysis, format_report


class SummarizeApp:
    """Tkinter interface for loading, summarizing, and saving text."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.current_path: Path | None = None
        self.root.title("SummarizeIT")
        self.root.geometry("1000x700")
        self.root.minsize(760, 520)

        self._build_layout()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=(12, 12, 12, 6))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(5, weight=1)

        ttk.Button(toolbar, text="Open file", command=self.open_file).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(toolbar, text="Summarize", command=self.summarize).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(toolbar, text="Save report", command=self.save_report).grid(
            row=0, column=2, padx=(0, 16)
        )
        ttk.Label(toolbar, text="Summary sentences:").grid(row=0, column=3)
        self.sentence_limit = tk.IntVar(value=3)
        ttk.Spinbox(
            toolbar, from_=1, to=20, textvariable=self.sentence_limit, width=5
        ).grid(row=0, column=4, padx=(6, 0))
        self.file_label = ttk.Label(toolbar, text="No file selected")
        self.file_label.grid(row=0, column=5, padx=(16, 0), sticky="e")

        content = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        content.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="nsew")

        input_frame = ttk.Labelframe(content, text="Document", padding=8)
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)
        self.input_text = tk.Text(input_frame, wrap="word", undo=True)
        self.input_text.grid(row=0, column=0, sticky="nsew")
        input_scrollbar = ttk.Scrollbar(
            input_frame, orient="vertical", command=self.input_text.yview
        )
        input_scrollbar.grid(row=0, column=1, sticky="ns")
        self.input_text.configure(yscrollcommand=input_scrollbar.set)
        content.add(input_frame, weight=1)

        output_frame = ttk.Labelframe(content, text="Report", padding=8)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.output_text = tk.Text(output_frame, wrap="word", state="disabled")
        self.output_text.grid(row=0, column=0, sticky="nsew")
        output_scrollbar = ttk.Scrollbar(
            output_frame, orient="vertical", command=self.output_text.yview
        )
        output_scrollbar.grid(row=0, column=1, sticky="ns")
        self.output_text.configure(yscrollcommand=output_scrollbar.set)
        content.add(output_frame, weight=1)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w").grid(
            row=2, column=0, padx=12, pady=(0, 8), sticky="ew"
        )

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open text document",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            text = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            messagebox.showerror("Open failed", "The selected file is not valid UTF-8.")
            return
        except OSError as error:
            messagebox.showerror("Open failed", str(error))
            return

        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", text)
        self.current_path = Path(path)
        self.file_label.configure(text=self.current_path.name)
        self.status.set(f"Loaded {self.current_path.name}")

    def summarize(self) -> None:
        try:
            limit = self.sentence_limit.get()
            if limit < 1:
                raise ValueError
        except (tk.TclError, ValueError):
            messagebox.showerror("Summarize failed", "Sentence count must be at least 1.")
            return

        text = self.input_text.get("1.0", tk.END).strip()
        analysis = extract_analysis(text, max_points=limit)
        report = format_report(analysis, " ".join(analysis.key_points))
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", report)
        self.output_text.configure(state="disabled")
        self.status.set("Summary generated")

    def save_report(self) -> None:
        report = self.output_text.get("1.0", tk.END).strip()
        if not report:
            messagebox.showinfo("Save report", "Generate a summary before saving the report.")
            return

        initial_name = (
            f"{self.current_path.stem} report.txt"
            if self.current_path
            else "summary report.txt"
        )
        path = filedialog.asksaveasfilename(
            title="Save report",
            initialfile=initial_name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            Path(path).write_text(report + "\n", encoding="utf-8")
        except OSError as error:
            messagebox.showerror("Save failed", str(error))
            return
        self.status.set(f"Saved {Path(path).name}")


def main() -> None:
    root = tk.Tk()
    SummarizeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()