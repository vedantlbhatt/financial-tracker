"""
Financial Tracker - Upload bank statements (CSV/Excel), categorize, and visualize.
Run with: streamlit run app.py
"""

import csv
import io

import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Financial Tracker", page_icon="📊", layout="wide")

# ============ CATEGORIZATION RULES (no LLM needed) ============
DEFAULT_CATEGORY_RULES = {
    "Food & Dining": ["restaurant", "uber eats", "doordash", "grubhub", "starbucks", "mcdonald", "chipotle", "groceries", "whole foods", "trader joe", "safeway", "kroger", "food"],
    "Transportation": ["gas", "shell", "chevron", "exxon", "uber", "lyft", "parking", "toll", "transit", "metro", "bus", "car wash"],
    "Shopping": ["amazon", "target", "walmart", "costco", "best buy", "ebay", "etsy"],
    "Bills & Utilities": ["electric", "water", "internet", "phone", "verizon", "att", "t-mobile", "rent", "mortgage", "insurance"],
    "Entertainment": ["netflix", "spotify", "hulu", "disney", "hbo", "prime video", "steam", "playstation", "xbox", "movie", "concert"],
    "Health": ["pharmacy", "cvs", "walgreens", "doctor", "hospital", "gym", "health"],
    "Travel": ["airline", "hotel", "airbnb", "booking", "expedia", "delta", "united", "american airlines"],
    "Subscriptions": ["subscription", "monthly", "annual", "membership"],
}


def categorize_description(description: str, rules: dict) -> str:
    if pd.isna(description) or not str(description).strip():
        return "Uncategorized"
    text = str(description).lower()
    for category, keywords in rules.items():
        for kw in keywords:
            if kw in text:
                return category
    return "Uncategorized"


def load_bofa_checking(uploaded_file) -> pd.DataFrame | None:
    """Load BofA checking CSV. Skips first 6 rows (summary block), parses transaction table.

    Handles rows where the Description contains commas (e.g. Zelle memos) by merging
    extra fields into the description instead of skipping the row.
    """
    try:
        content = uploaded_file.read().decode("utf-8", errors="replace")
        uploaded_file.seek(0)
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        if len(rows) < 8:
            st.error("File too short to contain transaction data.")
            return None

        # Skip first 6 summary rows; row 6 is header
        data_rows = rows[7:]

        records = []
        for row in data_rows:
            if len(row) < 4:
                continue
            # If row has extra fields (e.g. commas in description), merge middle into description
            # Format: Date, Description..., Amount, Running Bal.
            date_str = row[0].strip()
            if len(row) == 4:
                description = row[1].strip()
                amount_str = row[2].strip()
            else:
                description = ", ".join(row[1 : -2]).strip()
                amount_str = row[-2].strip()

            if "beginning balance" in description.lower():
                continue
            if not amount_str:
                continue

            amount = pd.to_numeric(amount_str.replace(",", ""), errors="coerce")
            if pd.isna(amount):
                continue

            date = pd.to_datetime(date_str, format="mixed", errors="coerce")
            if pd.isna(date):
                continue

            records.append({"date": date, "description": description, "amount": amount})

        if not records:
            st.error("No valid transactions found in file.")
            return None

        df = pd.DataFrame(records)
        df["_source"] = getattr(uploaded_file, "name", "bofa_checking")
        return df
    except Exception as e:
        st.error(f"Could not parse BofA checking file: {e}")
        return None


def load_table(uploaded_file) -> pd.DataFrame | None:
    """Load generic CSV or Excel file."""
    try:
        name = getattr(uploaded_file, "name", "") or ""
        if name.lower().endswith(".csv"):
            return pd.read_csv(uploaded_file)
        xl = pd.ExcelFile(uploaded_file)
        dfs = []
        for sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet)
            if not df.empty and len(df.columns) >= 2:
                df["_sheet"] = sheet
                dfs.append(df)
        if dfs:
            return pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        return pd.read_excel(uploaded_file) if uploaded_file else None
    except Exception as e:
        st.error(f"Could not parse file: {e}")
        return None


# ============ UI ============
st.title("📊 Financial Tracker")
st.caption("Upload bank statements • Categorize • View trends")

source_format = st.radio(
    "Source format",
    ["BofA Checking", "Generic (CSV/Excel)"],
    horizontal=True,
    help="BofA Checking: auto-parses their CSV format (skips summary rows). Generic: manual column mapping.",
)

uploaded_files = st.file_uploader(
    "Upload file(s)",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True,
    help="BofA: upload multiple monthly CSVs to merge. Generic: single file.",
)

if uploaded_files:
    # Normalize to list (single file returns one item)
    files = list(uploaded_files)

    if source_format == "BofA Checking":
        # Only CSV supported for BofA
        csv_files = [f for f in files if getattr(f, "name", "").lower().endswith(".csv")]
        if not csv_files:
            st.warning("BofA Checking format requires CSV files. Please upload .csv exports.")
        else:
            dfs = []
            for f in csv_files:
                df = load_bofa_checking(f)
                if df is not None:
                    dfs.append(df)
            if dfs:
                df = pd.concat(dfs, ignore_index=True).sort_values("date")
                st.success(f"Loaded {len(df)} transactions from {len(csv_files)} file(s)")

                # BofA: negative = debit (expense), positive = credit. For spending, use debits only.
                df_spend = df[df["amount"] < 0].copy()
                df_spend["amount"] = df_spend["amount"].abs()
                df_spend["category"] = df_spend["description"].apply(
                    lambda x: categorize_description(x, DEFAULT_CATEGORY_RULES)
                )

                if df_spend.empty:
                    st.info("No debit (expense) transactions found in the uploaded files.")
                else:
                    # Editable rules
                    with st.expander("Edit category rules (keyword → category)"):
                        rules_text = "\n".join([f"{cat}: {', '.join(kws)}" for cat, kws in DEFAULT_CATEGORY_RULES.items()])
                        edited = st.text_area("Rules", value=rules_text, height=200)
                        if st.button("Apply rules"):
                            try:
                                new_rules = {}
                                for line in edited.strip().split("\n"):
                                    if ":" in line:
                                        cat, rest = line.split(":", 1)
                                        new_rules[cat.strip()] = [k.strip().lower() for k in rest.split(",") if k.strip()]
                                if new_rules:
                                    df_spend["category"] = df_spend["description"].apply(
                                        lambda x: categorize_description(x, new_rules)
                                    )
                                    st.rerun()
                            except Exception as e:
                                st.warning(f"Could not parse rules: {e}")

                    # Summary
                    st.subheader("Spending by category")
                    summary = df_spend.groupby("category")["amount"].sum().sort_values(ascending=False).reset_index()
                    col1, col2 = st.columns(2)
                    with col1:
                        st.dataframe(summary, use_container_width=True, hide_index=True)
                    with col2:
                        fig = px.pie(summary, values="amount", names="category", title="Spending by category")
                        st.plotly_chart(fig, use_container_width=True)

                    # Trends
                    st.subheader("Spending over time")
                    monthly = df_spend.groupby([df_spend["date"].dt.to_period("M"), "category"])["amount"].sum().reset_index()
                    monthly["date"] = monthly["date"].astype(str)
                    fig_trend = px.line(monthly, x="date", y="amount", color="category", title="Monthly spending by category")
                    st.plotly_chart(fig_trend, use_container_width=True)

                    # Raw data
                    with st.expander("View raw transactions"):
                        st.dataframe(df, use_container_width=True, hide_index=True)

    else:
        # Generic: single file or merge by columns
        if len(files) > 1:
            st.info("Generic mode: using first file. For multi-file merge, use BofA Checking format.")
        uploaded = files[0]
        df = load_table(uploaded)
        if df is not None:
            st.success(f"Loaded {len(df)} rows, {len(df.columns)} columns")

            st.subheader("Column mapping")
            amount_col = st.selectbox("Amount column", options=df.columns.tolist(), index=0)
            desc_col = st.selectbox("Description column", options=df.columns.tolist(), index=min(1, len(df.columns) - 1))
            date_candidates = [c for c in df.columns if "date" in str(c).lower() or "time" in str(c).lower()]
            date_idx = df.columns.tolist().index(date_candidates[0]) if date_candidates else 0
            date_col = st.selectbox("Date column", options=df.columns.tolist(), index=date_idx)

            df["amount"] = pd.to_numeric(df[amount_col], errors="coerce")
            df["description"] = df[desc_col].astype(str)
            df["date"] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=["amount", "date"])
            df["amount"] = df["amount"].abs()
            df["category"] = df["description"].apply(lambda x: categorize_description(x, DEFAULT_CATEGORY_RULES))

            with st.expander("Edit category rules"):
                rules_text = "\n".join([f"{cat}: {', '.join(kws)}" for cat, kws in DEFAULT_CATEGORY_RULES.items()])
                edited = st.text_area("Rules", value=rules_text, height=200)
                if st.button("Apply rules"):
                    try:
                        new_rules = {}
                        for line in edited.strip().split("\n"):
                            if ":" in line:
                                cat, rest = line.split(":", 1)
                                new_rules[cat.strip()] = [k.strip().lower() for k in rest.split(",") if k.strip()]
                        if new_rules:
                            df["category"] = df["description"].apply(lambda x: categorize_description(x, new_rules))
                            st.rerun()
                    except Exception as e:
                        st.warning(f"Could not parse rules: {e}")

            st.subheader("Summary by category")
            summary = df.groupby("category")["amount"].sum().sort_values(ascending=False).reset_index()
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(summary, use_container_width=True, hide_index=True)
            with col2:
                fig = px.pie(summary, values="amount", names="category", title="Spending by category")
                st.plotly_chart(fig, use_container_width=True)

            st.subheader("Spending over time")
            monthly = df.groupby([df["date"].dt.to_period("M"), "category"])["amount"].sum().reset_index()
            monthly["date"] = monthly["date"].astype(str)
            fig_trend = px.line(monthly, x="date", y="amount", color="category", title="Monthly spending by category")
            st.plotly_chart(fig_trend, use_container_width=True)

            with st.expander("View raw data"):
                st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.info("👆 Choose a source format and upload file(s). BofA Checking supports multiple CSVs (e.g. Jan, Feb, Mar) to merge.")
