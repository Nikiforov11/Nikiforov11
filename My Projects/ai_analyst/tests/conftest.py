import pandas as pd
import pytest

from core.config import Settings
from data_layer.loader import clean_dataframe
from scripts.make_sample_data import make_sales


@pytest.fixture
def orders() -> pd.DataFrame:
    """Tiny hand-made dataset: small enough to compute expected answers by hand.

    Revenue by region: North 3010, South 20, East 150, (missing) 1100. Total 4280.
    March 2024 has no orders (tests zero-filling of time series).
    """
    return pd.DataFrame({
        "order_date": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-10",
                                      "2024-04-01", "2024-04-15", "2025-01-10"]),
        "region": pd.Series(["North", "South", "North", "East", "North", None], dtype="string"),
        "product": pd.Series(["Laptop", "Pen", "Laptop", "Chair", "Pen", "Laptop"], dtype="string"),
        "quantity": [1, 10, 2, 1, 5, 1],
        "revenue": [1000.0, 20.0, 2000.0, 150.0, 10.0, 1100.0],
    })


@pytest.fixture(scope="session")
def sales() -> pd.DataFrame:
    """Realistic generated data, passed through the same cleaning as uploads."""
    raw = make_sales(n_orders=600, seed=1)
    raw["Order Date"] = raw["Order Date"].dt.strftime("%Y-%m-%d")
    df, _ = clean_dataframe(raw.astype(str))
    return df


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch) -> Settings:
    """Point all storage at a temporary folder for the duration of a test."""
    s = Settings(data_dir=tmp_path)
    for module in ("core.config", "data_layer.loader", "data_layer.ingest"):
        monkeypatch.setattr(f"{module}.settings", s)
    return s
