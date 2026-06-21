# Fact-Check Agent

A Streamlit web app that reads a PDF, extracts quantified claims, searches the live web, and classifies each claim as `Verified`, `Inaccurate`, or `False`.

## What it does

- Extracts claims containing statistics, dates, financial figures, percentages, user counts, and technical quantities.
- Searches live web results for each claim.
- Compares claim quantities against source snippets.
- Produces an evidence-backed report with source links, matched figures, and alternative figures/dates when the claim appears outdated or wrong.
- Runs without paid API keys.

## How verdicts work

- `Verified`: top web evidence repeats the key quantity/date and is topically aligned.
- `Inaccurate`: related evidence exists, but the figures or dates differ.
- `False`: no strong supporting evidence or corroborating quantity was found in the top results.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud

1. Push this repository to GitHub.
2. In Streamlit Cloud, create a new app from the repository.
3. Set the main file path to `app.py`.
4. Deploy and share the public app URL.

## Repository structure

```text
app.py              Streamlit interface
factcheck.py        PDF extraction, claim extraction, web search, verdict scoring
requirements.txt    Deployment dependencies
tests/              Focused unit tests for extraction and verdict logic
```

## Notes

DuckDuckGo results can occasionally rate-limit automated traffic. Re-run the check or reduce sources per claim if live search is temporarily unavailable.
