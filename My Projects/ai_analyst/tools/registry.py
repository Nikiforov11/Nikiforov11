"""The tool registry: the single list of everything the agent can do.

In Phase 2 the agent loop will:
  1. build Gemini function declarations from TOOLS (name, description,
     input model's JSON schema),
  2. receive a function call like {"name": "aggregate_data", "args": {...}},
  3. hand it to `run_tool`, which validates the args and runs the tool.

Validation errors come back as a ToolResult the LLM can read and correct,
exactly like errors from inside a tool.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd
from pydantic import BaseModel, ValidationError

from core.schemas import (AggregateInput, ChartSpec, ColumnStatsInput, ComparePeriodsInput,
                          DistinctValuesInput, TimeSeriesInput, ToolResult)
from tools.analysis import (aggregate_data, compare_periods, distinct_values,
                            get_column_statistics, time_series)
from tools.charts import prepare_chart_data


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    fn: Callable[[pd.DataFrame, Any], ToolResult]


TOOLS: dict[str, ToolSpec] = {t.name: t for t in [
    ToolSpec(
        "get_column_statistics",
        "Summary statistics for one column (sum, mean, median, min, max for numbers; "
        "date range for dates; most frequent values for text), optionally filtered.",
        ColumnStatsInput, get_column_statistics,
    ),
    ToolSpec(
        "aggregate_data",
        "Group rows by one or more columns and aggregate a metric, e.g. total revenue by region "
        "or number of orders per product. Returns the top groups, their share of the total, "
        "and the grand total.",
        AggregateInput, aggregate_data,
    ),
    ToolSpec(
        "time_series",
        "Aggregate a metric over time (day/week/month/quarter/year), optionally split by one "
        "column. Use for trends, seasonality, best/worst periods.",
        TimeSeriesInput, time_series,
    ),
    ToolSpec(
        "compare_periods",
        "Compare a metric between two date ranges (e.g. this year vs last year, Q2 vs Q1), "
        "overall and optionally per group, with absolute and percentage change.",
        ComparePeriodsInput, compare_periods,
    ),
    ToolSpec(
        "distinct_values",
        "List the values of a column with their counts, optionally searching for text. "
        "Call this before filtering on a text column to get the exact spelling.",
        DistinctValuesInput, distinct_values,
    ),
    ToolSpec(
        "create_chart",
        "Create a chart (bar, line, pie, scatter, histogram). Describe what to plot; the data "
        "is computed automatically. Use when a visual helps or the user asks for one.",
        ChartSpec, prepare_chart_data,
    ),
]}


def _format_validation_error(e: ValidationError) -> str:
    parts = []
    for err in e.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "input"
        parts.append(f"{loc}: {err['msg']}")
    return "Invalid arguments: " + "; ".join(parts)


def run_tool(name: str, df: pd.DataFrame, args: dict[str, Any] | None) -> ToolResult:
    spec = TOOLS.get(name)
    if spec is None:
        return ToolResult.failure(f"Unknown tool '{name}'. Available: {', '.join(TOOLS)}")
    try:
        params = spec.input_model.model_validate(args or {})
    except ValidationError as e:
        return ToolResult.failure(_format_validation_error(e))
    return spec.fn(df, params)
