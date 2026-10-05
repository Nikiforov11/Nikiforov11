"""Pydantic models shared by every layer of the app.

Why Pydantic instead of plain dicts?
  * Inputs from the LLM get validated *before* touching pandas, and the
    validation message is clear enough for the LLM to fix its own call.
  * In Phase 2 these same models generate Gemini's function declarations,
    so the schema the model sees and the schema we enforce can never drift.
  * Everything serializes to JSON, which Inngest steps require (Phase 3).
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from core.config import settings


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class AggFunc(str, Enum):
    SUM = "sum"
    MEAN = "mean"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    COUNT = "count"          # number of non-null values (or rows if no metric)
    NUNIQUE = "nunique"      # number of distinct values, e.g. unique customers


class FilterOperator(str, Enum):
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GE = ">="
    LE = "<="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"    # case-insensitive substring match
    BETWEEN = "between"      # inclusive, value = [low, high]


class TimeGrain(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

    @property
    def pandas_period(self) -> str:
        return {"day": "D", "week": "W", "month": "M", "quarter": "Q", "year": "Y"}[self.value]


class SortOrder(str, Enum):
    DESC = "desc"
    ASC = "asc"


class ColumnKind(str, Enum):
    NUMERIC = "numeric"
    DATETIME = "datetime"
    CATEGORICAL = "categorical"   # few distinct values: region, product...
    TEXT = "text"                 # free text / high cardinality
    BOOLEAN = "boolean"


class ColumnRole(str, Enum):
    """Business meaning of a column. This is what makes the app schema-agnostic:
    the agent reasons about 'the revenue column', whatever it is called."""
    DATE = "date"
    REVENUE = "revenue"
    QUANTITY = "quantity"
    PRICE = "price"
    COST = "cost"
    PROFIT = "profit"
    DISCOUNT = "discount"
    PRODUCT = "product"
    CATEGORY = "category"
    CUSTOMER = "customer"
    REGION = "region"
    CHANNEL = "channel"
    ID = "id"
    OTHER = "other"


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
Scalar = Union[str, float, int, bool]


class Filter(BaseModel):
    column: str = Field(description="Exact column name to filter on.")
    operator: FilterOperator
    value: Union[Scalar, list[Scalar]] = Field(
        description="Value to compare with. A list for 'in'/'not_in', "
                    "and a [low, high] pair for 'between'. Dates as 'YYYY-MM-DD'."
    )

    @model_validator(mode="after")
    def _check_value_shape(self) -> "Filter":
        is_list = isinstance(self.value, list)
        if self.operator in (FilterOperator.IN, FilterOperator.NOT_IN) and not is_list:
            self.value = [self.value]          # be forgiving: wrap a single value
        if self.operator == FilterOperator.BETWEEN and not (is_list and len(self.value) == 2):
            raise ValueError("'between' needs a [low, high] list with exactly 2 values")
        if is_list and self.operator not in (
            FilterOperator.IN, FilterOperator.NOT_IN, FilterOperator.BETWEEN
        ):
            raise ValueError(f"operator '{self.operator.value}' takes a single value, not a list")
        return self


# --------------------------------------------------------------------------- #
# Tool inputs
# --------------------------------------------------------------------------- #
class ColumnStatsInput(BaseModel):
    column: str = Field(description="Exact column name.")
    filters: list[Filter] = Field(default_factory=list)


class AggregateInput(BaseModel):
    group_by: list[str] = Field(min_length=1, description="One or more columns to group by.")
    metric: Optional[str] = Field(
        default=None, description="Column to aggregate. Omit with agg='count' to count rows."
    )
    agg: AggFunc = AggFunc.SUM
    filters: list[Filter] = Field(default_factory=list)
    top_n: int = Field(default=settings.default_top_n, ge=1, le=settings.max_result_rows)
    sort: SortOrder = SortOrder.DESC

    @field_validator("group_by", mode="before")
    @classmethod
    def _str_to_list(cls, v: Any) -> Any:
        return [v] if isinstance(v, str) else v

    @model_validator(mode="after")
    def _metric_required(self) -> "AggregateInput":
        if self.metric is None and self.agg != AggFunc.COUNT:
            raise ValueError(f"'metric' is required when agg is '{self.agg.value}'")
        return self


class TimeSeriesInput(BaseModel):
    date_column: str = Field(description="A date column, usually the main date column.")
    metric: Optional[str] = Field(default=None, description="Omit with agg='count' to count rows.")
    agg: AggFunc = AggFunc.SUM
    grain: TimeGrain = TimeGrain.MONTH
    group_by: Optional[str] = Field(default=None, description="Optional column to split the series by.")
    top_groups: int = Field(default=5, ge=1, le=10, description="Max number of series when grouping.")
    filters: list[Filter] = Field(default_factory=list)

    @model_validator(mode="after")
    def _metric_required(self) -> "TimeSeriesInput":
        if self.metric is None and self.agg != AggFunc.COUNT:
            raise ValueError(f"'metric' is required when agg is '{self.agg.value}'")
        return self


class DateRange(BaseModel):
    start: date
    end: date = Field(description="Inclusive end date.")

    @model_validator(mode="after")
    def _ordered(self) -> "DateRange":
        if self.start > self.end:
            raise ValueError("start must be on or before end")
        return self


class ComparePeriodsInput(BaseModel):
    date_column: str = Field(description="A date column, usually the main date column.")
    metric: Optional[str] = Field(default=None, description="Omit with agg='count' to count rows.")
    agg: AggFunc = AggFunc.SUM
    base_period: DateRange = Field(description="The earlier / reference period.")
    compare_period: DateRange = Field(description="The period compared against the base.")
    group_by: Optional[str] = Field(default=None, description="Optional column to compare per group.")
    top_n: int = Field(default=settings.default_top_n, ge=1, le=settings.max_result_rows)
    filters: list[Filter] = Field(default_factory=list)

    @model_validator(mode="after")
    def _metric_required(self) -> "ComparePeriodsInput":
        if self.metric is None and self.agg != AggFunc.COUNT:
            raise ValueError(f"'metric' is required when agg is '{self.agg.value}'")
        return self


class DistinctValuesInput(BaseModel):
    column: str = Field(description="Exact column name.")
    search: Optional[str] = Field(default=None, description="Optional text to look for in the values.")
    limit: int = Field(default=20, ge=1, le=settings.max_result_rows)


class ChartSpec(BaseModel):
    """What the LLM asks for. The data itself is computed by our code,
    never invented by the model."""
    chart_type: ChartType
    title: str
    x: str = Field(description="Column for the x-axis (pie: the category column).")
    y: Optional[str] = Field(default=None, description="Metric column. Not used by histogram.")
    agg: AggFunc = AggFunc.SUM
    color: Optional[str] = Field(default=None, description="Optional column to split into series.")
    grain: Optional[TimeGrain] = Field(default=None, description="Time grain when x is a date column.")
    top_n: int = Field(default=settings.default_top_n, ge=1, le=settings.max_result_rows)
    filters: list[Filter] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_combination(self) -> "ChartSpec":
        t = self.chart_type
        if t == ChartType.HISTOGRAM and self.y is not None:
            raise ValueError("histogram uses only 'x'; remove 'y'")
        if t == ChartType.SCATTER and self.y is None:
            raise ValueError("scatter needs both 'x' and 'y'")
        if t == ChartType.PIE and self.color is not None:
            raise ValueError("pie charts cannot use 'color'")
        if t in (ChartType.BAR, ChartType.LINE, ChartType.PIE) \
                and self.y is None and self.agg != AggFunc.COUNT:
            raise ValueError(f"'{t.value}' needs 'y' unless agg is 'count'")
        return self


# --------------------------------------------------------------------------- #
# Tool output
# --------------------------------------------------------------------------- #
class ToolResult(BaseModel):
    """Every tool returns this shape, success or failure.

    The LLM always gets something it can read: data on success, or an error
    message (often with suggestions) it can use to retry.
    """
    ok: bool
    data: Any = None
    error: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    rows_used: Optional[int] = Field(default=None, description="Rows left after filtering.")

    @classmethod
    def success(cls, data: Any, rows_used: int | None = None,
                warnings: list[str] | None = None) -> "ToolResult":
        return cls(ok=True, data=data, rows_used=rows_used, warnings=warnings or [])

    @classmethod
    def failure(cls, error: str, warnings: list[str] | None = None) -> "ToolResult":
        return cls(ok=False, error=error, warnings=warnings or [])


# --------------------------------------------------------------------------- #
# Dataset profile
# --------------------------------------------------------------------------- #
class ColumnProfile(BaseModel):
    name: str
    dtype: str
    kind: ColumnKind
    role: ColumnRole = ColumnRole.OTHER
    missing: int
    unique: int
    # numeric
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    # datetime
    date_min: Optional[str] = None
    date_max: Optional[str] = None
    # categorical / text
    top_values: Optional[dict[str, int]] = None


class DatasetProfile(BaseModel):
    dataset_id: str
    rows: int
    columns: int
    column_profiles: list[ColumnProfile]
    sample_rows: list[dict[str, Any]]
    primary_date: Optional[str] = None       # best guess for "the" date column
    primary_metric: Optional[str] = None     # best guess for "the" sales value column
    cleaning_notes: list[str] = Field(default_factory=list)

    def column(self, name: str) -> ColumnProfile | None:
        return next((c for c in self.column_profiles if c.name == name), None)

    def columns_with_role(self, role: ColumnRole) -> list[str]:
        return [c.name for c in self.column_profiles if c.role == role]
