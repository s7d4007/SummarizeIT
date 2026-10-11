# Mini AI Agent

`mini_agent.py` is a small, dependency-free Python agent that reads a UTF-8
text file, extracts key information, and creates an extractive summary. It
uses sentence scoring based on the most frequent meaningful words, so it works
offline and does not require an API key.

## Usage

```powershell
python mini_agent.py document.txt
python mini_agent.py document.txt --sentences 5 --output report.txt
```

The report contains:

- the first sentence as the document title;
- the most important sentences as the summary and key points;
- the five most frequent non-stop-word keywords;
- dates found in common numeric and written formats.

## Tests

Run the standard-library test suite from the project directory:

```powershell
python -m unittest discover -s tests -v
```
