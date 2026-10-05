"""Shared building blocks for every tool."""
from __future__ import annotations

import difflib
import functools
from typing import Callable

import pandas as pd

from core.errors import ToolError
from core.schemas import AggFunc, ToolResult


def tool(fn: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
    """Guarantee a tool never raises: errors become ToolResult(ok=False).

    ToolError messages are written for the LLM, so they're passed as-is.
    Unexpected exceptions are reported with their type, which is what you
    will look for first when debugging a run in Inngest.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> ToolResult:
        try:
            return fn(*args, **kwargs)
        except ToolError as e:
            return ToolResult.failure(str(e))
        except Exception as e:  # noqa: BLE001 - last line of defence
            return ToolResult.failure(f"Internal error in {fn.__name__}: {type(e).__name__}: {e}")
    return wrapper


def resolve_column(df: pd.DataFrame, name: str, warnings: list[str] | None = None) -> str:
    """Return the real column name, forgiving case/spacing differences.

    'Order Date' -> 'order_date' is resolved silently (with a warning);
    a truly unknown name raises ToolError with the closest suggestions,
    so the LLM can retry with the right one.
    """
    if name in df.columns:
        return name
    wanted = name.strip().lower().replace(" ", "_").replace("-", "_")
    for col in df.columns:
        if str(col).lower() == wanted:
            if warnings is not None:
                warnings.append(f"Column '{name}' interpreted as '{col}'.")
            return col
    close = difflib.get_close_matches(wanted, [str(c) for c in df.columns], n=3, cutoff=0.5)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    raise ToolError(f"Column '{name}' not found.{hint} Available columns: {', '.join(map(str, df.columns))}")


def require_numeric(df: pd.DataFrame, column: str, agg: AggFunc) -> None:
    """sum/mean/median need numbers; min/max/count/nunique work on anything."""
    if agg in (AggFunc.SUM, AggFunc.MEAN, AggFunc.MEDIAN) \
            and not pd.api.types.is_numeric_dtype(df[column]):
        raise ToolError(
            f"Cannot compute '{agg.value}' of '{column}' because it is not numeric "
            f"(dtype {df[column].dtype}). Use agg='count' or 'nunique', or pick a numeric column."
        )
    if pd.api.types.is_bool_dtype(df[column]) and agg != AggFunc.COUNT:
        raise ToolError(f"'{column}' is yes/no; filter on it or use agg='count'.")


def require_datetime(df: pd.DataFrame, column: str) -> None:
    if not pd.api.types.is_datetime64_any_dtype(df[column]):
        raise ToolError(f"Column '{column}' is not a date column (dtype {df[column].dtype}).")


def aggregate_series(grouped, metric: str | None, agg: AggFunc) -> pd.Series:
    """Run an aggregation on a DataFrameGroupBy. With no metric and
    agg='count', count rows per group."""
    if metric is None:
        return grouped.size()
    return grouped[metric].agg(agg.value)


def ensure_rows(df: pd.DataFrame, context: str = "") -> None:
    if df.empty:
        raise ToolError(
            "No rows match the filters" + (f" {context}" if context else "") +
            ". Check filter values with the distinct_values tool."
        )
