"""Starter questions built from the profile, without spending an LLM call.

They show a new user what kind of questions work, and they're phrased with
the dataset's real column meanings ("revenue by region"), not generic text.
"""
from __future__ import annotations

from core.schemas import ColumnRole, DatasetProfile

GROUP_ROLES = [ColumnRole.REGION, ColumnRole.PRODUCT, ColumnRole.CATEGORY, ColumnRole.CHANNEL]


def _label(name: str) -> str:
    return name.replace("_", " ")


def suggest_questions(profile: DatasetProfile, limit: int = 4) -> list[str]:
    metric = profile.primary_metric
    date = profile.column(profile.primary_date) if profile.primary_date else None
    groups = [c for role in GROUP_ROLES for c in profile.columns_with_role(role)]
    customers = profile.columns_with_role(ColumnRole.CUSTOMER)

    questions: list[str] = []
    if metric and groups:
        questions.append(f"Which {_label(groups[0])} has the highest {_label(metric)}?")
    if metric and date:
        questions.append(f"Show the monthly trend of {_label(metric)} as a chart.")
    if metric and date and date.date_min and date.date_max and date.date_min[:4] != date.date_max[:4]:
        last = int(date.date_max[:4])
        target = _label(groups[1] if len(groups) > 1 else groups[0]) if groups else None
        questions.append(f"How did {_label(metric)} change from {last - 1} to {last}"
                         + (f" by {target}?" if target else "?"))
    if customers:
        questions.append(f"How many unique {_label(customers[0])}s are there, "
                         f"and who are the top 5?")
    if metric:
        questions.append(f"What is the average {_label(metric)} per row, and how is it distributed?")
    if not questions:
        questions.append("Summarize this dataset: what's in it and what stands out?")
    return questions[:limit]
