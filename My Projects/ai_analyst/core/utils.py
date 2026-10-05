"""Helpers to turn pandas/numpy values into plain JSON-safe Python values.

pandas results contain numpy ints, Timestamps, NaN, Periods... none of which
survive json.dumps (and Inngest steps must return JSON). Every tool passes
its output through `to_jsonable` before returning it.
"""
import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, pd.DataFrame):
        return to_jsonable(value.to_dict(orient="records"))
    if isinstance(value, pd.Series):
        return to_jsonable(value.tolist())
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        # Drop the time part when it's midnight: '2024-03-01' reads better.
        if value.hour == value.minute == value.second == 0:
            return value.strftime("%Y-%m-%d")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, pd.Period):
        return str(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else round(f, 4)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value
