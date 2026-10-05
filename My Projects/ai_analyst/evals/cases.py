"""Eval cases for the sample dataset (scripts/make_sample_data.py).

Each expected value is *computed from the data with pandas*, never typed in
by hand, so the cases stay correct if you change the generator.

A case:
  id         short unique name
  question   what the user asks
  history    optional earlier questions, asked first (tests follow-ups)
  expect     function(df) -> dict with any of:
               numbers        values that must appear in the answer
               rel_tol/abs_tol tolerance for those numbers (default 1% relative)
               mentions       words that must all appear
               mentions_any   at least one of these must appear
               uses_tools_any at least one of these tools must be used successfully
               chart          True/False: a chart must / must not be produced

Add a case whenever you 👎 an answer in the app: `python -m evals.run --feedback`
lists them.
"""
from __future__ import annotations

import pandas as pd


def _year(df: pd.DataFrame, year: int) -> pd.DataFrame:
    return df[df["order_date"].dt.year == year]


def _top(series: pd.Series) -> str:
    return str(series.idxmax())


CASES = [
    {
        "id": "total_revenue",
        "question": "What is the total revenue in the dataset?",
        "expect": lambda df: {"numbers": [df["revenue"].sum()]},
    },
    {
        "id": "top_region_2024",
        "question": "Which region had the highest revenue in 2024, and how much?",
        "expect": lambda df: {
            "mentions": [_top(_year(df, 2024).groupby("region")["revenue"].sum())],
            "numbers": [_year(df, 2024).groupby("region")["revenue"].sum().max()],
        },
    },
    {
        "id": "yoy_growth",
        "question": "By what percentage did revenue grow from 2023 to 2024?",
        "expect": lambda df: {
            "numbers": [(_year(df, 2024)["revenue"].sum() / _year(df, 2023)["revenue"].sum() - 1) * 100],
            "abs_tol": 0.2,
            "uses_tools_any": ["compare_periods", "time_series", "aggregate_data"],
        },
    },
    {
        "id": "best_month_2024",
        "question": "What was the best month of 2024 by revenue?",
        "expect": lambda df: {
            "mentions_any": [
                pd.Timestamp(year=2024, month=int(
                    _year(df, 2024).groupby(df["order_date"].dt.month)["revenue"].sum().idxmax()),
                    day=1).strftime(fmt)
                for fmt in ("%B", "%b", "%Y-%m")],
        },
    },
    {
        "id": "unique_customers",
        "question": "How many unique customers are there?",
        "expect": lambda df: {"numbers": [df["customer"].nunique()], "rel_tol": 0.0, "abs_tol": 0.5},
    },
    {
        "id": "average_order_value",
        "question": "What is the average revenue per order?",
        "expect": lambda df: {"numbers": [df["revenue"].mean()]},
    },
    {
        "id": "online_share",
        "question": "What share of total revenue comes from the Online channel?",
        "expect": lambda df: {
            "numbers": [df.loc[df["channel"] == "Online", "revenue"].sum() / df["revenue"].sum() * 100],
            "abs_tol": 0.2,
        },
    },
    {
        "id": "top_products_by_units",
        "question": "List the top 3 products by units sold.",
        "expect": lambda df: {
            "mentions": [str(p) for p in df.groupby("product")["quantity"].sum().nlargest(3).index],
        },
    },
    {
        "id": "spanish_question",
        "question": "¿Qué categoría tuvo más ventas en 2023?",
        "expect": lambda df: {
            "mentions": [_top(_year(df, 2023).groupby("category")["revenue"].sum())],
        },
    },
    {
        "id": "fuzzy_filter",
        "question": "How much revenue did laptops make in the east region?",
        "expect": lambda df: {
            "numbers": [df.loc[df["product"].str.contains("Laptop") & (df["region"] == "East"),
                               "revenue"].sum()],
        },
    },
    {
        "id": "chart_request",
        "question": "Show me the monthly revenue trend as a chart.",
        "expect": lambda df: {"chart": True, "uses_tools_any": ["create_chart"]},
    },
    {
        "id": "follow_up",
        "history": ["What was the total revenue in 2023?"],
        "question": "And in 2024?",
        "expect": lambda df: {"numbers": [_year(df, 2024)["revenue"].sum()]},
    },
    {
        "id": "not_answerable",
        "question": "What was our profit margin by region?",
        "expect": lambda df: {
            "mentions_any": ["cost", "profit data", "not available", "doesn't contain",
                             "does not contain", "no profit", "isn't available", "not possible"],
        },
    },
]
