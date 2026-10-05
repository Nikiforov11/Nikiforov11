import json

import plotly.graph_objects as go
import pytest

from tools.charts import build_figure
from tools.registry import TOOLS, run_tool

# One valid call per tool, used to check every tool end to end.
VALID_CALLS = {
    "get_column_statistics": {"column": "revenue"},
    "aggregate_data": {"group_by": ["region"], "metric": "revenue"},
    "time_series": {"date_column": "order_date", "metric": "revenue", "group_by": "channel"},
    "compare_periods": {"date_column": "order_date", "metric": "revenue", "group_by": "region",
                        "base_period": {"start": "2023-01-01", "end": "2023-12-31"},
                        "compare_period": {"start": "2024-01-01", "end": "2024-12-31"}},
    "distinct_values": {"column": "product"},
    "create_chart": {"chart_type": "bar", "title": "Revenue by region", "x": "region", "y": "revenue"},
}


def test_every_registered_tool_has_a_test_call():
    assert set(TOOLS) == set(VALID_CALLS)


@pytest.mark.parametrize("name", list(VALID_CALLS))
def test_every_tool_returns_json_serializable_results(sales, name):
    """Inngest step outputs must be JSON. This catches numpy/Timestamp leaks."""
    result = run_tool(name, sales, VALID_CALLS[name])
    assert result.ok, result.error
    json.dumps(result.model_dump(mode="json"))


@pytest.mark.parametrize("name", list(TOOLS))
def test_input_models_produce_json_schema(name):
    """Phase 2 turns these schemas into Gemini function declarations."""
    schema = TOOLS[name].input_model.model_json_schema()
    assert schema["type"] == "object"
    assert schema["properties"]


def test_invalid_arguments_come_back_as_a_readable_result(sales):
    result = run_tool("aggregate_data", sales, {"group_by": ["region"], "agg": "average"})
    assert not result.ok
    assert result.error.startswith("Invalid arguments")
    assert "agg" in result.error


def test_unknown_tool(sales):
    result = run_tool("delete_everything", sales, {})
    assert not result.ok and "Unknown tool" in result.error


@pytest.mark.parametrize("spec", [
    {"chart_type": "bar", "title": "t", "x": "region", "y": "revenue"},
    {"chart_type": "bar", "title": "t", "x": "region", "y": "revenue", "color": "channel"},
    {"chart_type": "line", "title": "t", "x": "order_date", "y": "revenue", "grain": "quarter"},
    {"chart_type": "line", "title": "t", "x": "order_date", "y": "revenue", "color": "category"},
    {"chart_type": "pie", "title": "t", "x": "product", "y": "revenue", "top_n": 3},
    {"chart_type": "scatter", "title": "t", "x": "quantity", "y": "revenue", "color": "category"},
    {"chart_type": "histogram", "title": "t", "x": "revenue"},
    {"chart_type": "bar", "title": "t", "x": "category", "agg": "count"},
])
def test_charts_build_figures(sales, spec):
    result = run_tool("create_chart", sales, spec)
    assert result.ok, result.error
    fig = build_figure(result.data)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_pie_adds_other_slice(sales):
    result = run_tool("create_chart", sales,
                      {"chart_type": "pie", "title": "t", "x": "product", "y": "revenue", "top_n": 3})
    labels = [r["product"] for r in result.data["records"]]
    assert labels[-1] == "Other" and len(labels) == 4


@pytest.mark.parametrize("bad_spec", [
    {"chart_type": "histogram", "title": "t", "x": "revenue", "y": "quantity"},
    {"chart_type": "scatter", "title": "t", "x": "quantity"},
    {"chart_type": "pie", "title": "t", "x": "region", "y": "revenue", "color": "channel"},
])
def test_invalid_chart_specs_are_rejected(sales, bad_spec):
    assert not run_tool("create_chart", sales, bad_spec).ok
