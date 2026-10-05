"""Apply a list of Filter objects to a DataFrame.

Compared to the first version:
  * unknown columns raise a clear error instead of being silently skipped
    (a skipped filter = a confident, wrong answer);
  * values are converted to the column's type ('2024-01-01' becomes a date,
    '100' becomes a number);
  * text comparisons ignore case and surrounding spaces, because the LLM
    will write 'north' when the data says 'North'.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from core.errors import ToolError
from core.schemas import Filter, FilterOperator as Op
from tools.base import resolve_column


def _coerce(value: Any, s: pd.Series, column: str) -> Any:
    if isinstance(value, list):
        return [_coerce(v, s, column) for v in value]
    if pd.api.types.is_datetime64_any_dtype(s):
        try:
            return pd.Timestamp(value)
        except (ValueError, TypeError):
            raise ToolError(f"'{value}' is not a valid date for '{column}'. Use YYYY-MM-DD.")
    if pd.api.types.is_bool_dtype(s):
        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "1", "si", "sí"}
        return bool(value)
    if pd.api.types.is_numeric_dtype(s):
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ToolError(f"'{value}' is not a number, but '{column}' is numeric.")
    return str(value).strip().casefold()


def _is_text(s: pd.Series) -> bool:
    return not (pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s)
                or pd.api.types.is_bool_dtype(s))


def _mask(s: pd.Series, op: Op, value: Any) -> pd.Series:
    text = _is_text(s)
    if text:
        s = s.astype("string").str.strip().str.casefold()

    if op == Op.EQ:
        m = s == value
    elif op == Op.NE:
        m = s != value
    elif op in (Op.GT, Op.LT, Op.GE, Op.LE):
        if text:
            raise ToolError(f"Operator '{op.value}' needs a numeric or date column.")
        m = {Op.GT: s > value, Op.LT: s < value, Op.GE: s >= value, Op.LE: s <= value}[op]
    elif op == Op.IN:
        m = s.isin(value)
    elif op == Op.NOT_IN:
        m = ~s.isin(value)
    elif op == Op.CONTAINS:
        if not text:
            raise ToolError("Operator 'contains' only works on text columns.")
        m = s.str.contains(str(value), regex=False)
    elif op == Op.BETWEEN:
        low, high = value
        if text:
            raise ToolError("Operator 'between' needs a numeric or date column.")
        if pd.api.types.is_datetime64_any_dtype(s) and high == high.normalize():
            # 'between 2024-01-01 and 2024-01-31' should include all of Jan 31.
            m = (s >= low) & (s < high + pd.Timedelta(days=1))
        else:
            m = s.between(low, high)
    else:  # pragma: no cover - the enum makes this unreachable
        raise ToolError(f"Unsupported operator '{op}'.")

    # Comparisons with missing values give <NA>; treat them as "no match".
    return m.fillna(False).astype(bool)


def apply_filters(df: pd.DataFrame, filters: list[Filter] | None,
                  warnings: list[str] | None = None) -> pd.DataFrame:
    if not filters:
        return df
    out = df
    for f in filters:
        col = resolve_column(out, f.column, warnings)
        value = _coerce(f.value, out[col], col)
        out = out[_mask(out[col], f.operator, value)]
    return out
