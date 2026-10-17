# Mini AI Agent

`mini_agent.py` is a small, dependency-free Python agent that reads a UTF-8 text file, extracts key information, and creates an extractive summary. It uses sentence scoring based on the most frequent meaningful words, so it works offline and does not require an API key.

## Windows setup and usage

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/).
During installation, enable **Add Python to PATH**. Open a new PowerShell window after installation and verify that Python is available:

```powershell
py --version
```

The `py` launcher is the recommended Windows command because it selects the installed Python 3 interpreter reliably. This project has no third-party dependencies, so there is no package-installation step or virtual environment required.

## Usage

### Desktop app

Double-click `summarize_it.pyw` to open the desktop app without using a terminal. Use **Open file** to load a UTF-8 text document, or paste text into the document area. Choose the summary length, click **Summarize**, and use **Save report** to export the result.

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
