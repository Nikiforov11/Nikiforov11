import pandas as pd

from core.schemas import ColumnKind, ColumnRole
from data_layer.profiler import add_derived_columns, profile_dataset, to_prompt_context


def test_roles_on_english_columns(sales):
    profile = profile_dataset(sales, "test")
    roles = {c.name: c.role for c in profile.column_profiles}
    assert roles["order_date"] == ColumnRole.DATE
    assert roles["order_id"] == ColumnRole.ID
    assert roles["revenue"] == ColumnRole.REVENUE
    assert roles["unit_price"] == ColumnRole.PRICE
    assert roles["quantity"] == ColumnRole.QUANTITY
    assert roles["region"] == ColumnRole.REGION
    assert roles["category"] == ColumnRole.CATEGORY
    assert profile.primary_date == "order_date"
    assert profile.primary_metric == "revenue"


def test_roles_on_spanish_columns():
    df = pd.DataFrame({
        "fecha": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "importe_total": [10.0, 20.0],
        "cliente": pd.Series(["A", "B"], dtype="string"),
        "provincia": pd.Series(["Barcelona", "Girona"], dtype="string"),
        "cantidad": [1, 2],
    })
    roles = {c.name: c.role for c in profile_dataset(df, "x").column_profiles}
    assert roles == {
        "fecha": ColumnRole.DATE, "importe_total": ColumnRole.REVENUE,
        "cliente": ColumnRole.CUSTOMER, "provincia": ColumnRole.REGION,
        "cantidad": ColumnRole.QUANTITY,
    }


def test_status_column_is_not_an_id():
    df = pd.DataFrame({"order_status": pd.Series(["open", "closed"] * 50, dtype="string")})
    col = profile_dataset(df, "x").column_profiles[0]
    assert col.role != ColumnRole.ID
    assert col.kind == ColumnKind.CATEGORICAL


def test_revenue_is_derived_from_price_and_quantity():
    df = pd.DataFrame({"unit_price": [2.0, 3.0], "qty": [10, 1]})
    out, notes = add_derived_columns(df)
    assert out["revenue"].tolist() == [20.0, 3.0]
    assert notes


def test_existing_revenue_is_not_overwritten(sales):
    out, notes = add_derived_columns(sales)
    assert notes == []
    assert out is sales


def test_profile_is_deterministic(sales):
    assert profile_dataset(sales, "a").model_dump() == profile_dataset(sales, "a").model_dump()


def test_prompt_context_is_compact_and_informative(sales):
    context = to_prompt_context(profile_dataset(sales, "x"))
    assert "Main sales value column: revenue" in context
    assert "order_date [datetime, role=date]" in context
    assert len(context) < 3000   # it is sent with every question
