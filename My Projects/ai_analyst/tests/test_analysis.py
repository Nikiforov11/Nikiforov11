import pytest

from core.schemas import (AggregateInput, ColumnStatsInput, ComparePeriodsInput,
                          DistinctValuesInput, TimeSeriesInput)
from tools.analysis import (aggregate_data, compare_periods, distinct_values,
                            get_column_statistics, time_series)


# ---- aggregate_data -------------------------------------------------------- #
def test_sum_by_region_matches_hand_calculation(orders):
    r = aggregate_data(orders, AggregateInput(group_by="region", metric="revenue"))
    assert r.ok
    rows = {row["region"]: row["sum_revenue"] for row in r.data["rows"]}
    assert rows == {"North": 3010, "(missing)": 1100, "East": 150, "South": 20}
    assert r.data["grand_total"] == 4280
    assert r.data["rows"][0]["share_pct"] == pytest.approx(70.33, abs=0.01)


def test_sum_matches_pandas_on_realistic_data(sales):
    r = aggregate_data(sales, AggregateInput(group_by=["category"], metric="revenue", top_n=50))
    expected = sales.groupby("category")["revenue"].sum().round(4).to_dict()
    assert {row["category"]: row["sum_revenue"] for row in r.data["rows"]} == pytest.approx(expected)


def test_top_n_truncates_and_reports_others(orders):
    r = aggregate_data(orders, AggregateInput(group_by="region", metric="revenue", top_n=2))
    assert len(r.data["rows"]) == 2
    assert r.data["total_groups"] == 4
    assert r.data["others_total"] == 170
    assert r.warnings


def test_count_rows_without_metric(orders):
    r = aggregate_data(orders, AggregateInput(group_by="product", agg="count"))
    assert {row["product"]: row["row_count"] for row in r.data["rows"]} == {"Laptop": 3, "Pen": 2, "Chair": 1}


def test_ascending_sort(orders):
    r = aggregate_data(orders, AggregateInput(group_by="region", metric="revenue", sort="asc"))
    assert r.data["rows"][0]["region"] == "South"


def test_sum_of_text_column_is_a_readable_error(orders):
    r = aggregate_data(orders, AggregateInput(group_by="region", metric="product"))
    assert not r.ok
    assert "not numeric" in r.error


def test_filter_that_matches_nothing(orders):
    r = aggregate_data(orders, AggregateInput(
        group_by="region", metric="revenue",
        filters=[{"column": "product", "operator": "==", "value": "Phone"}]))
    assert not r.ok
    assert "distinct_values" in r.error


def test_metric_required_unless_count():
    with pytest.raises(ValueError):
        AggregateInput(group_by="region", agg="sum")


# ---- time_series ----------------------------------------------------------- #
def test_monthly_series_fills_empty_months_with_zero(orders):
    r = time_series(orders, TimeSeriesInput(date_column="order_date", metric="revenue", grain="month"))
    points = {p["period"]: p["sum_revenue"] for p in r.data["points"]}
    assert len(points) == 13                     # 2024-01 .. 2025-01
    assert points["2024-01"] == 1020
    assert points["2024-03"] == 0
    assert r.data["summary"]["peak_period"] == "2024-02"


def test_series_split_by_group(orders):
    r = time_series(orders, TimeSeriesInput(date_column="order_date", metric="revenue",
                                             grain="year", group_by="product", top_groups=2))
    assert {p["product"] for p in r.data["points"]} == {"Laptop", "Chair"}
    assert len(r.data["points"]) == 4            # 2 years x 2 products
    assert r.warnings


def test_too_many_points_asks_for_coarser_grain(sales):
    r = time_series(sales, TimeSeriesInput(date_column="order_date", metric="revenue", grain="day"))
    assert not r.ok
    assert "coarser grain" in r.error


def test_time_series_on_non_date_column(orders):
    r = time_series(orders, TimeSeriesInput(date_column="region", metric="revenue"))
    assert not r.ok


# ---- compare_periods ------------------------------------------------------- #
def test_compare_two_periods(orders):
    r = compare_periods(orders, ComparePeriodsInput(
        date_column="order_date", metric="revenue",
        base_period={"start": "2024-01-01", "end": "2024-02-29"},
        compare_period={"start": "2024-04-01", "end": "2024-04-30"},
        group_by="region"))
    overall = r.data["overall"]
    assert (overall["base_value"], overall["compare_value"]) == (3020, 160)
    assert overall["change_pct"] == pytest.approx(-94.7, abs=0.01)
    north = next(g for g in r.data["groups"] if g["region"] == "North")
    assert (north["base_value"], north["compare_value"]) == (3000, 10)
    assert r.data["groups"][0]["region"] == "North"   # biggest mover first


def test_period_outside_data_warns(orders):
    r = compare_periods(orders, ComparePeriodsInput(
        date_column="order_date", metric="revenue",
        base_period={"start": "2020-01-01", "end": "2020-12-31"},
        compare_period={"start": "2024-01-01", "end": "2024-12-31"}))
    assert r.ok
    assert r.data["overall"]["change_pct"] is None   # can't divide by zero
    assert any("no rows" in w for w in r.warnings)


def test_period_start_after_end_is_rejected():
    with pytest.raises(ValueError):
        ComparePeriodsInput(date_column="d", metric="m",
                            base_period={"start": "2024-02-01", "end": "2024-01-01"},
                            compare_period={"start": "2024-01-01", "end": "2024-01-31"})


# ---- get_column_statistics ------------------------------------------------- #
def test_numeric_statistics_with_filter(orders):
    r = get_column_statistics(orders, ColumnStatsInput(
        column="revenue", filters=[{"column": "region", "operator": "==", "value": "North"}]))
    assert r.data["sum"] == 3010
    assert r.data["count"] == 3
    assert r.rows_used == 3


def test_text_and_date_statistics(orders):
    text = get_column_statistics(orders, ColumnStatsInput(column="product"))
    assert text.data["top_values"]["Laptop"] == 3
    dates = get_column_statistics(orders, ColumnStatsInput(column="order_date"))
    assert dates.data["min"] == "2024-01-05"


# ---- distinct_values ------------------------------------------------------- #
def test_distinct_values_search_and_typos(orders):
    found = distinct_values(orders, DistinctValuesInput(column="product", search="lap"))
    assert [v["value"] for v in found.data["values"]] == ["Laptop"]
    typo = distinct_values(orders, DistinctValuesInput(column="product", search="laptp"))
    assert [v["value"] for v in typo.data["values"]] == ["Laptop"]
    assert typo.warnings
