# SummarizeIT

`mini_agent.py` is a small Python agent that reads a UTF-8 text file, extracts key information, and creates an extractive summary. It uses sentence scoring based on the most frequent meaningful words, so it works offline and does not require an API key. `gui.py` provides the optional PySide6 desktop application.

## Windows setup and usage

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/).
During installation, enable **Add Python to PATH**. Open a new PowerShell window after installation and verify that Python is available:

```powershell
py --version
```

The `py` launcher is the recommended Windows command because it selects the installed Python 3 interpreter reliably. The command-line summarizer uses only the standard library. The desktop app requires PySide6.

## Install as a command-line tool

From the project directory, install the offline CLI:

```powershell
py -m pip install .
```

This adds the `summarizeit` command:

```powershell
summarizeit document.txt --sentences 5 --output report.txt
```

To install the desktop application command as well, install the optional GUI dependency:

```powershell
py -m pip install ".[gui]"
summarizeit-gui
```

The existing `py mini_agent.py ...` and `pyw summarize_it.pyw` launch paths remain supported for running directly from a checkout.

## Desktop app setup

Install the GUI dependency from the project directory:

```powershell
py -m pip install -r requirements.txt
```

Then double-click `summarize_it.pyw`, or launch it with:

```powershell
pyw summarize_it.pyw
```

The app supports opening and saving UTF-8 text files, drag-and-drop loading,
editable document input, configurable summary length, keyboard shortcuts, and
a dark Qt interface with native file dialogs. The summarization logic remains
in `mini_agent.py` and is shared by both the CLI and the GUI.

## Dependencies and attribution

The GUI has one direct dependency:

- **PySide6**, version 6.12.0, licensed under the GNU Lesser
  General Public License v3.0 (LGPL-3.0), GNU General Public License v3.0
  (GPL-3.0), or a commercial Qt license. PySide6 provides the Qt for Python
  bindings and the Qt desktop libraries used by this application. See the
  [PySide6 licensing page](https://doc.qt.io/qtforpython-6/licenses.html) and
  the [Qt licensing page](https://www.qt.io/licensing) for the official terms.

Installing PySide6 also installs its official runtime components, including
`PySide6_Essentials`, `PySide6_Addons`, `PySide6_Pdf`, `PySide6_WebEngine`, and
`shiboken6`. Those packages are distributed by the Qt for Python project and
are covered by the same available LGPL/GPL/commercial licensing model. This
project does not bundle modified Qt source, third-party icon packs, fonts, or
images. The interface uses Qt's built-in standard icons and platform dialogs.

When distributing the desktop app, keep the PySide6 license notices and the
corresponding Qt license texts with the distribution, and comply with the
license option selected for your deployment. The application code in this
repository is separate from Qt and does not change Qt's license terms.

## Usage

### Desktop app

Double-click `summarize_it.pyw` to open the desktop app without using a terminal. Use **Open document** to load a UTF-8 text document, or paste text into the document area. Choose the summary length, click **Generate summary**, and use **Save report** to export the result.

Open PowerShell in the project folder. For example, if the repository is in
`C:\Users\YourName\SummarizeIT`:

```powershell
Set-Location "C:\Users\YourName\SummarizeIT"
```

Use quotation marks around paths that contain spaces. The input file must be a UTF-8 text file.

```powershell
py mini_agent.py document.txt
py mini_agent.py document.txt --sentences 5 --output report.txt
py mini_agent.py "C:\Users\YourName\Documents\meeting notes.txt" `
  --output "C:\Users\YourName\Documents\meeting report.txt"
```

To see all available options:

```powershell
py mini_agent.py --help
```

Without `--output`, the report is printed in the terminal. With `--output`, the report is written as UTF-8 text to the specified path; an existing file at that path is overwritten.

The report contains:

- the first sentence as the document title;
- the most important sentences as the summary and key points;
- the five most frequent non-stop-word keywords;
- dates found in common numeric and written formats.

If you use Command Prompt instead of PowerShell, run the same commands with `py`. Keep a command on one line, or use Command Prompt's continuation character (`^`) instead of PowerShell's backtick:

```bat
py mini_agent.py document.txt --sentences 5 --output report.txt
```

## Tests

Run the standard-library test suite from the project directory:

```powershell
py -m unittest discover -s tests -v
```

If `py` is not recognized, reopen the terminal after installing Python or use `python` if that command is available on your machine.

## Build distributions

Install the optional packaging tools and build a wheel and source archive:

```powershell
py -m pip install ".[build]"
py -m build
```

The generated files are placed in `dist`. To create a Windows desktop executable, install the GUI and packaging extras, then run:

```powershell
py -m pip install ".[gui,build]"
pyinstaller --noconsole --onefile --name SummarizeIT summarize_it.pyw
```

The executable is written to `dist\SummarizeIT.exe`. Keep the PySide6 and Qt license notices with any distributed desktop build.