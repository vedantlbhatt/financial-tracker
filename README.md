# Financial Tracker

Upload Excel expense sheets, categorize spending, and view trends. Built for easy local use.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens in your browser at http://localhost:8501. Data stays on your machine.

## Features

- **Excel upload** – .xlsx and .xls (bank exports, manual spreadsheets)
- **Auto column detection** – Pick amount, description, and date columns
- **Rule-based categorization** – Keyword matching (no LLM needed)
- **Editable rules** – Add your own merchants/keywords in the UI
- **Charts** – Pie chart by category, line chart for trends over time
