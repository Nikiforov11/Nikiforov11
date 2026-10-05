"""Charts in two halves.

1. `prepare_chart_data(df, spec)`  - runs on the worker. The LLM only says
   *what* to plot (a ChartSpec); our code computes the numbers, reusing the
   analysis tools. Output is small JSON (ChartData), so it can travel through
   Inngest to the UI.
2. `build_figure(chart_data)`      - runs in Streamlit. Turns ChartData into
   an interactive Plotly figure. No pandas logic, no LLM involved.

This replaces "let the LLM write matplotlib code": safer, cheaper in tokens,
and every chart is guaranteed to show real numbers.
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pydantic import BaseModel

from core.config import settings
from core.errors import ToolError
from core.schemas import (AggregateInput, ChartSpec, ChartType, TimeGrain,
                          TimeSeriesInput, ToolResult)
from core.utils import to_jsonable
from tools.analysis import aggregate_data, time_series
from tools.base import ensure_rows, resolve_column, tool
from tools.filters import apply_filters

HISTOGRAM_BINS = 20
MAX_COLOR_SERIES = 8
# Ledger green first, then colours that stay distinguishable next to it.
PALETTE = ["#1F7A55", "#3C6E9F", "#C98B2B", "#7A4E7E", "#5FA88A", "#8FA9C8", "#B5654A", "#8A958F"]


class ChartData(BaseModel):
    """Render-ready chart: everything Streamlit needs, nothing more."""
    chart_type: ChartType
    title: str
    x_field: str
    y_field: Optional[str] = None
    color_field: Optional[str] = None
    records: list[dict[str, Any]]


def _unwrap(result: ToolResult) -> Any:
    if not result.ok:
        raise ToolError(result.error)
    return result.data


def _histogram(data: pd.DataFrame, x: str) -> list[dict]:
    values = data[x].dropna().astype("float64")
    if values.empty:
        raise ToolError(f"'{x}' has no values to plot.")
    counts, edges = np.histogram(values, bins=HISTOGRAM_BINS)
    return [{"bin": f"{edges[i]:,.4g} – {edges[i + 1]:,.4g}", "count": int(c)}
            for i, c in enumerate(counts)]


def _scatter(data: pd.DataFrame, x: str, y: str, color: str | None) -> list[dict]:
    cols = [x, y] + ([color] if color else [])
    points = data[cols].dropna(subset=[x, y])
    if len(points) > settings.max_scatter_points:
        points = points.sample(settings.max_scatter_points, random_state=42)
    return points.to_dict(orient="records")


def _categorical(data: pd.DataFrame, spec: ChartSpec, x: str, y: str | None,
                 color: str | None) -> tuple[list[dict], str]:
    """Bar/pie over categories. With a color split, keep the top_n x values
    and the top colour values, so the chart stays readable."""
    if color is None:
        result = _unwrap(aggregate_data(data, AggregateInput(
            group_by=[x], metric=y, agg=spec.agg, top_n=spec.top_n)))
        value_col = result["value_column"]
        records = [{x: r[x], value_col: r[value_col]} for r in result["rows"]]
        if spec.chart_type == ChartType.PIE and result.get("others_total"):
            records.append({x: "Other", value_col: result["others_total"]})
        return records, value_col

    top_x = _unwrap(aggregate_data(data, AggregateInput(
        group_by=[x], metric=y, agg=spec.agg, top_n=spec.top_n)))
    top_c = _unwrap(aggregate_data(data, AggregateInput(
        group_by=[color], metric=y, agg=spec.agg, top_n=MAX_COLOR_SERIES)))
    keep_x = {r[x] for r in top_x["rows"]}
    keep_c = {r[color] for r in top_c["rows"]}
    subset = data[data[x].astype(str).isin({str(v) for v in keep_x})
                  & data[color].astype(str).isin({str(v) for v in keep_c})]
    result = _unwrap(aggregate_data(subset, AggregateInput(
        group_by=[x, color], metric=y, agg=spec.agg, top_n=settings.max_result_rows)))
    value_col = result["value_column"]
    return [{x: r[x], color: r[color], value_col: r[value_col]} for r in result["rows"]], value_col


@tool
def prepare_chart_data(df: pd.DataFrame, spec: ChartSpec) -> ToolResult:
    warnings: list[str] = []
    data = apply_filters(df, spec.filters, warnings)
    x = resolve_column(data, spec.x, warnings)
    y = resolve_column(data, spec.y, warnings) if spec.y else None
    color = resolve_column(data, spec.color, warnings) if spec.color else None
    ensure_rows(data)
    x_is_date = pd.api.types.is_datetime64_any_dtype(data[x])

    if spec.chart_type == ChartType.HISTOGRAM:
        if not pd.api.types.is_numeric_dtype(data[x]):
            raise ToolError(f"Histogram needs a numeric column; '{x}' is not numeric.")
        records, x_field, y_field = _histogram(data, x), "bin", "count"

    elif spec.chart_type == ChartType.SCATTER:
        for col in (x, y):
            if not pd.api.types.is_numeric_dtype(data[col]):
                raise ToolError(f"Scatter needs numeric columns; '{col}' is not numeric.")
        records, x_field, y_field = _scatter(data, x, y, color), x, y

    elif x_is_date and spec.chart_type != ChartType.PIE:
        result = _unwrap(time_series(data, TimeSeriesInput(
            date_column=x, metric=y, agg=spec.agg, grain=spec.grain or TimeGrain.MONTH,
            group_by=color, top_groups=min(spec.top_n, MAX_COLOR_SERIES))))
        records, x_field, y_field = result["points"], "period", result["value_column"]

    else:
        if spec.chart_type == ChartType.LINE:
            warnings.append(f"Line chart over a non-date x ('{x}'); a bar chart may read better.")
        records, y_field = _categorical(data, spec, x, y, color)
        x_field = x

    chart = ChartData(chart_type=spec.chart_type, title=spec.title, x_field=x_field,
                      y_field=y_field, color_field=color, records=to_jsonable(records))
    return ToolResult.success(chart.model_dump(mode="json"), rows_used=len(data), warnings=warnings)


def _label(name: str | None) -> str:
    return (name or "").replace("_", " ").capitalize()


def build_figure(chart: ChartData | dict) -> go.Figure:
    """Pure presentation: ChartData -> Plotly figure."""
    if isinstance(chart, dict):
        chart = ChartData.model_validate(chart)
    frame = pd.DataFrame(chart.records)
    labels = {c: _label(c) for c in frame.columns}
    common = dict(labels=labels, title=chart.title, color_discrete_sequence=PALETTE)
    if chart.color_field:
        frame[chart.color_field] = frame[chart.color_field].astype(str)

    t = chart.chart_type
    if t == ChartType.PIE:
        fig = px.pie(frame, names=chart.x_field, values=chart.y_field, **common)
    elif t == ChartType.LINE:
        fig = px.line(frame, x=chart.x_field, y=chart.y_field, color=chart.color_field,
                      markers=True, **common)
    elif t == ChartType.SCATTER:
        fig = px.scatter(frame, x=chart.x_field, y=chart.y_field, color=chart.color_field,
                         opacity=0.7, **common)
    else:  # BAR and HISTOGRAM (pre-binned)
        fig = px.bar(frame, x=chart.x_field, y=chart.y_field, color=chart.color_field,
                     barmode="group", **common)
        if t == ChartType.HISTOGRAM:
            fig.update_layout(bargap=0.02)
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), legend_title_text=_label(chart.color_field),
                      font_family="IBM Plex Sans, system-ui, sans-serif",
                      title_font_family="IBM Plex Serif, Georgia, serif")
    return fig
