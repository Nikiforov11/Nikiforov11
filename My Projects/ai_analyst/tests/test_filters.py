import pytest
from pydantic import ValidationError

from core.errors import ToolError
from core.schemas import Filter
from tools.filters import apply_filters


def F(column, operator, value):
    return Filter(column=column, operator=operator, value=value)


def test_no_filters_returns_all_rows(orders):
    assert len(apply_filters(orders, [])) == len(orders)


def test_text_equality_ignores_case_and_spaces(orders):
    assert len(apply_filters(orders, [F("region", "==", "  north ")])) == 3


def test_not_equal_excludes_missing_values(orders):
    # 6 rows: 3 North, 1 South, 1 East, 1 missing -> != North keeps South and East.
    # Missing values are "unknown", so they are never counted as a match.
    assert len(apply_filters(orders, [F("region", "!=", "North")])) == 2


def test_in_accepts_single_value(orders):
    f = F("product", "in", "pen")
    assert f.value == ["pen"]
    assert len(apply_filters(orders, [f])) == 2


def test_numeric_value_given_as_string(orders):
    assert len(apply_filters(orders, [F("revenue", ">=", "1000")])) == 3


def test_between_dates_includes_whole_end_day(orders):
    out = apply_filters(orders, [F("order_date", "between", ["2024-01-01", "2024-01-20"])])
    assert len(out) == 2


def test_contains(orders):
    assert len(apply_filters(orders, [F("product", "contains", "LAP")])) == 3


def test_filters_are_combined_with_and(orders):
    out = apply_filters(orders, [F("region", "==", "North"), F("product", "==", "Laptop")])
    assert out["revenue"].sum() == 3000


def test_unknown_column_raises_with_suggestion(orders):
    with pytest.raises(ToolError, match="Did you mean: region"):
        apply_filters(orders, [F("regin", "==", "North")])


def test_bad_date_raises(orders):
    with pytest.raises(ToolError, match="not a valid date"):
        apply_filters(orders, [F("order_date", ">", "last tuesday")])


def test_greater_than_on_text_raises(orders):
    with pytest.raises(ToolError):
        apply_filters(orders, [F("region", ">", "A")])


def test_between_requires_two_values():
    with pytest.raises(ValidationError):
        F("revenue", "between", [1])
