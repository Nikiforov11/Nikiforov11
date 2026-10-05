"""The analysis tools the agent can call.

Each tool:
  * takes the DataFrame plus a validated Pydantic input model,
  * raises ToolError for problems the LLM can fix (the @tool decorator
    converts it into ToolResult(ok=False)),
  * returns small, JSON-safe results with explicit column names, so the
    LLM never has to guess what a number means.
"""
from __future__ import annotations

import difflib

import pandas as pd

from core.config import settings
from core.errors import ToolError
from core.schemas import (AggFunc, AggregateInput, ColumnStatsInput, ComparePeriodsInput,
                          DateRange, DistinctValuesInput, SortOrder, TimeGrain,
                          TimeSeriesInput, ToolResult)
from core.utils import to_jsonable
from tools.base import (aggregate_series, ensure_rows, require_datetime, require_numeric,
                        resolve_column, tool)
from tools.filters import apply_filters

MISSING_LABEL = "(missing)"
ADDITIVE = (AggFunc.SUM, AggFunc.COUNT)   # aggregations where shares and zero-filling make sense


def _value_name(metric: str | None, agg: AggFunc) -> str:
    return "row_count" if metric is None else f"{agg.value}_{metric}"


def _pct_change(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or pd.isna(old) or pd.isna(new) or old == 0:
        return None
    return round((new - old) / abs(old) * 100, 2)


# --------------------------------------------------------------------------- #
# 1. Column statistics
# --------------------------------------------------------------------------- #
@tool
def get_column_statistics(df: pd.DataFrame, params: ColumnStatsInput) -> ToolResult:
    warnings: list[str] = []
    data = apply_filters(df, params.filters, warnings)
    col = resolve_column(data, params.column, warnings)
    ensure_rows(data)
    s = data[col]
    values = s.dropna()
    if values.empty:
        raise ToolError(f"Column '{col}' has no non-empty values after filtering.")

    stats: dict = {"column": col, "count": len(values), "missing": int(s.isna().sum())}
    if pd.api.types.is_bool_dtype(s):
        stats["true"] = int(values.sum())
        stats["false"] = int((~values.astype(bool)).sum())
    elif pd.api.types.is_numeric_dtype(s):
        v = values.astype("float64")
        stats.update(sum=v.sum(), mean=v.mean(), median=v.median(), min=v.min(), max=v.max(),
                     std=v.std(), p25=v.quantile(0.25), p75=v.quantile(0.75))
    elif pd.api.types.is_datetime64_any_dtype(s):
        stats.update(min=values.min(), max=values.max(),
                     span_days=int((values.max() - values.min()).days))
    else:
        counts = values.astype(str).value_counts()
        stats.update(unique=len(counts), top_values=counts.head(5).to_dict())

    return ToolResult.success(to_jsonable(stats), rows_used=len(data), warnings=warnings)


# --------------------------------------------------------------------------- #
# 2. Group-by aggregation
# --------------------------------------------------------------------------- #
def _group_frame(data: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Give missing group keys a visible label instead of silently dropping them."""
    out = data.copy()
    for c in group_cols:
        if out[c].isna().any() and not pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].astype("object").where(out[c].notna(), MISSING_LABEL)
    return out


@tool
def aggregate_data(df: pd.DataFrame, params: AggregateInput) -> ToolResult:
    warnings: list[str] = []
    data = apply_filters(df, params.filters, warnings)
    group_cols = [resolve_column(data, c, warnings) for c in params.group_by]
    metric = resolve_column(data, params.metric, warnings) if params.metric else None
    if metric:
        require_numeric(data, metric, params.agg)
    ensure_rows(data)

    grouped = _group_frame(data, group_cols).groupby(group_cols, observed=True, dropna=True)
    value_col = _value_name(metric, params.agg)
    result = aggregate_series(grouped, metric, params.agg).rename(value_col).reset_index()

    result = result.sort_values(value_col, ascending=params.sort == SortOrder.ASC,
                                na_position="last")
    total_groups = len(result)
    shown = result.head(params.top_n)

    payload: dict = {
        "group_by": group_cols,
        "value_column": value_col,
        "total_groups": total_groups,
        "rows": shown.to_dict(orient="records"),
    }
    if params.agg in ADDITIVE:
        grand_total = float(result[value_col].sum())
        payload["grand_total"] = grand_total
        if grand_total:
            payload["rows"] = [
                {**r, "share_pct": round(r[value_col] / grand_total * 100, 2)} for r in payload["rows"]
            ]
        if total_groups > params.top_n:
            payload["others_total"] = grand_total - float(shown[value_col].sum())
    if total_groups > params.top_n:
        warnings.append(f"Showing top {params.top_n} of {total_groups} groups.")

    return ToolResult.success(to_jsonable(payload), rows_used=len(data), warnings=warnings)


# --------------------------------------------------------------------------- #
# 3. Time series
# --------------------------------------------------------------------------- #
def _period_labels(periods: pd.Series | pd.Index, grain: TimeGrain) -> list[str]:
    if grain == TimeGrain.WEEK:   # '2024-01-01/2024-01-07' -> week start date
        return [p.start_time.strftime("%Y-%m-%d") for p in periods]
    return [str(p) for p in periods]   # '2024-01', '2024Q1', '2024', '2024-01-15'


@tool
def time_series(df: pd.DataFrame, params: TimeSeriesInput) -> ToolResult:
    warnings: list[str] = []
    data = apply_filters(df, params.filters, warnings)
    date_col = resolve_column(data, params.date_column, warnings)
    require_datetime(data, date_col)
    metric = resolve_column(data, params.metric, warnings) if params.metric else None
    if metric:
        require_numeric(data, metric, params.agg)
    group_col = resolve_column(data, params.group_by, warnings) if params.group_by else None

    data = data.dropna(subset=[date_col])
    ensure_rows(data)
    period = data[date_col].dt.to_period(params.grain.pandas_period).rename("period")
    full_range = pd.period_range(period.min(), period.max(), freq=period.dt.freq)
    if len(full_range) > settings.max_time_points:
        raise ToolError(
            f"{len(full_range)} {params.grain.value} periods is too many to return. "
            f"Use a coarser grain (week/month/quarter/year) or filter the date range."
        )

    value_col = _value_name(metric, params.agg)
    fill = 0 if params.agg in ADDITIVE else None   # a month with no sales = 0 sales

    if group_col is None:
        series = aggregate_series(data.groupby(period), metric, params.agg).reindex(full_range)
        if fill is not None:
            series = series.fillna(fill)
        points = [{"period": lbl, value_col: v}
                  for lbl, v in zip(_period_labels(series.index, params.grain), series.tolist())]
        values = series.dropna()
        summary = {}
        if not values.empty:
            peak, low = values.idxmax(), values.idxmin()
            summary = {
                "first_value": values.iloc[0], "last_value": values.iloc[-1],
                "change_pct_first_to_last": _pct_change(values.iloc[0], values.iloc[-1]),
                "peak_period": _period_labels([peak], params.grain)[0], "peak_value": values.max(),
                "lowest_period": _period_labels([low], params.grain)[0], "lowest_value": values.min(),
            }
        payload = {"grain": params.grain.value, "value_column": value_col,
                   "points": points, "summary": summary}
    else:
        grouped_data = _group_frame(data, [group_col])
        totals = aggregate_series(grouped_data.groupby(group_col, observed=True), metric, params.agg)
        top = totals.sort_values(ascending=False).head(params.top_groups).index
        if len(totals) > params.top_groups:
            warnings.append(f"Showing the top {params.top_groups} of {len(totals)} '{group_col}' values.")
        subset = grouped_data[grouped_data[group_col].isin(top)]
        sub_period = period.loc[subset.index]
        series = aggregate_series(subset.groupby([sub_period, group_col], observed=True),
                                  metric, params.agg)
        index = pd.MultiIndex.from_product([full_range, top], names=["period", group_col])
        series = series.reindex(index)
        if fill is not None:
            series = series.fillna(fill)
        frame = series.rename(value_col).reset_index()
        frame["period"] = _period_labels(frame["period"], params.grain)
        payload = {"grain": params.grain.value, "value_column": value_col, "group_by": group_col,
                   "points": frame.to_dict(orient="records")}

    return ToolResult.success(to_jsonable(payload), rows_used=len(data), warnings=warnings)


# --------------------------------------------------------------------------- #
# 4. Compare two periods
# --------------------------------------------------------------------------- #
def _in_range(dates: pd.Series, r: DateRange) -> pd.Series:
    start = pd.Timestamp(r.start)
    end_exclusive = pd.Timestamp(r.end) + pd.Timedelta(days=1)   # end date is inclusive
    return (dates >= start) & (dates < end_exclusive)


@tool
def compare_periods(df: pd.DataFrame, params: ComparePeriodsInput) -> ToolResult:
    warnings: list[str] = []
    data = apply_filters(df, params.filters, warnings)
    date_col = resolve_column(data, params.date_column, warnings)
    require_datetime(data, date_col)
    metric = resolve_column(data, params.metric, warnings) if params.metric else None
    if metric:
        require_numeric(data, metric, params.agg)
    group_col = resolve_column(data, params.group_by, warnings) if params.group_by else None
    ensure_rows(data)

    base = data[_in_range(data[date_col], params.base_period)]
    comp = data[_in_range(data[date_col], params.compare_period)]
    data_range = f"{data[date_col].min():%Y-%m-%d} to {data[date_col].max():%Y-%m-%d}"
    for label, part in (("base_period", base), ("compare_period", comp)):
        if part.empty:
            warnings.append(f"{label} has no rows. The data covers {data_range}.")

    value_col = _value_name(metric, params.agg)

    def total(part: pd.DataFrame):
        if part.empty:
            return 0 if params.agg in ADDITIVE else None
        if metric is None:
            return len(part)
        return part[metric].agg(params.agg.value)

    base_total, comp_total = total(base), total(comp)
    payload: dict = {
        "value_column": value_col,
        "base_period": params.base_period.model_dump(mode="json"),
        "compare_period": params.compare_period.model_dump(mode="json"),
        "overall": {
            "base_value": base_total, "compare_value": comp_total,
            "change": None if base_total is None or comp_total is None else comp_total - base_total,
            "change_pct": _pct_change(base_total, comp_total),
            "base_rows": len(base), "compare_rows": len(comp),
        },
    }

    if group_col:
        def by_group(part: pd.DataFrame) -> pd.Series:
            if part.empty:
                return pd.Series(dtype="float64")
            return aggregate_series(_group_frame(part, [group_col]).groupby(group_col, observed=True),
                                    metric, params.agg)

        table = pd.concat([by_group(base).rename("base_value"),
                           by_group(comp).rename("compare_value")], axis=1)
        if params.agg in ADDITIVE:
            table = table.fillna(0)
        table["change"] = table["compare_value"] - table["base_value"]
        table["change_pct"] = [_pct_change(b, c) for b, c in zip(table["base_value"], table["compare_value"])]
        # Biggest movers first, up or down.
        table = table.reindex(table["change"].abs().sort_values(ascending=False).index)
        payload["group_by"] = group_col
        payload["total_groups"] = len(table)
        payload["groups"] = table.head(params.top_n).rename_axis(group_col).reset_index().to_dict(orient="records")
        if len(table) > params.top_n:
            warnings.append(f"Showing the {params.top_n} biggest changes of {len(table)} groups.")

    return ToolResult.success(to_jsonable(payload), rows_used=len(base) + len(comp), warnings=warnings)


# --------------------------------------------------------------------------- #
# 5. Distinct values (lets the agent check spelling before filtering)
# --------------------------------------------------------------------------- #
@tool
def distinct_values(df: pd.DataFrame, params: DistinctValuesInput) -> ToolResult:
    warnings: list[str] = []
    col = resolve_column(df, params.column, warnings)
    counts = df[col].dropna().astype(str).value_counts()
    if counts.empty:
        raise ToolError(f"Column '{col}' has no values.")

    matches = counts
    if params.search:
        needle = params.search.strip().casefold()
        matches = counts[counts.index.str.casefold().str.contains(needle, regex=False)]
        if matches.empty:
            close = difflib.get_close_matches(needle, [v.casefold() for v in counts.index[:5000]],
                                              n=5, cutoff=0.6)
            lookup = {v.casefold(): v for v in counts.index}
            matches = counts[[lookup[c] for c in close]] if close else matches
            warnings.append(f"No value contains '{params.search}'." +
                            (" Showing the closest spellings." if close else ""))

    shown = matches.head(params.limit)
    payload = {
        "column": col,
        "total_distinct": len(counts),
        "matching": len(matches),
        "values": [{"value": v, "count": c} for v, c in shown.items()],
    }
    if len(matches) > params.limit:
        warnings.append(f"Showing {params.limit} of {len(matches)} values (most frequent first).")
    return ToolResult.success(to_jsonable(payload), rows_used=len(df), warnings=warnings)
