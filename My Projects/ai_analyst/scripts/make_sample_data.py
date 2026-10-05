"""Generate sample sales data for manual testing and (later) evals.

    python scripts/make_sample_data.py

Creates two files with the same underlying sales:
  data/sample_sales.csv     clean, US formats
  data/sample_sales_eu.csv  messy, European: ';' separator, '1.234,56 €',
                            dd/mm/yyyy dates, Spanish headers with accents
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from core.config import settings  # noqa: E402

PRODUCTS = {  # product: (category, base unit price)
    "Laptop Pro": ("Electronics", 1299.0), "Laptop Air": ("Electronics", 999.0),
    "Monitor 27": ("Electronics", 329.0), "Headphones": ("Electronics", 149.0),
    "Office Chair": ("Furniture", 249.0), "Standing Desk": ("Furniture", 549.0),
    "Bookshelf": ("Furniture", 119.0), "Notebook Pack": ("Stationery", 12.5),
    "Pen Set": ("Stationery", 8.9), "Desk Lamp": ("Furniture", 45.0),
}
REGIONS = {"North": 1.0, "South": 0.8, "East": 1.2, "West": 0.6}
CHANNELS = ["Online", "Retail", "Partner"]


def make_sales(n_orders: int = 3000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.date_range("2023-01-01", "2024-12-31", freq="D")
    # Seasonality: busy November-December, quiet in August, plus growth in 2024.
    weights = np.array([
        (1.6 if d.month in (11, 12) else 0.6 if d.month == 8 else 1.0) * (1.15 if d.year == 2024 else 1.0)
        for d in days])
    dates = rng.choice(days, size=n_orders, p=weights / weights.sum())

    region_names = list(REGIONS)
    region_p = np.array(list(REGIONS.values()))
    products = rng.choice(list(PRODUCTS), size=n_orders)
    qty = rng.integers(1, 6, size=n_orders)
    unit_price = np.array([PRODUCTS[p][1] for p in products]) * rng.uniform(0.95, 1.05, n_orders)
    discount = rng.choice([0, 0, 0, 0.05, 0.1, 0.15], size=n_orders)

    df = pd.DataFrame({
        "Order ID": [f"ORD-{i:05d}" for i in range(1, n_orders + 1)],
        "Order Date": pd.to_datetime(dates),
        "Customer": [f"CUST-{c:04d}" for c in rng.integers(1, 600, size=n_orders)],
        "Region": rng.choice(region_names, size=n_orders, p=region_p / region_p.sum()),
        "Channel": rng.choice(CHANNELS, size=n_orders, p=[0.5, 0.35, 0.15]),
        "Product": products,
        "Category": [PRODUCTS[p][0] for p in products],
        "Quantity": qty,
        "Unit Price": unit_price.round(2),
        "Discount": discount,
    })
    df["Revenue"] = (df["Quantity"] * df["Unit Price"] * (1 - df["Discount"])).round(2)
    return df.sort_values("Order Date").reset_index(drop=True)


def to_european(df: pd.DataFrame) -> pd.DataFrame:
    eu = df.rename(columns={
        "Order ID": "Nº Pedido", "Order Date": "Fecha", "Customer": "Cliente", "Region": "Región",
        "Channel": "Canal", "Product": "Producto", "Category": "Categoría", "Quantity": "Cantidad",
        "Unit Price": "Precio Unitario", "Discount": "Descuento", "Revenue": "Importe Total",
    }).copy()

    def money(v: float) -> str:   # 1234.5 -> '1.234,50 €'
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"

    eu["Fecha"] = eu["Fecha"].dt.strftime("%d/%m/%Y")
    eu["Precio Unitario"] = eu["Precio Unitario"].map(money)
    eu["Importe Total"] = eu["Importe Total"].map(money)
    eu["Descuento"] = (eu["Descuento"] * 100).map(lambda v: f"{v:g}%")
    return eu


if __name__ == "__main__":
    out_dir = settings.data_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    sales = make_sales()
    sales.to_csv(out_dir / "sample_sales.csv", index=False, date_format="%Y-%m-%d")
    to_european(sales).to_csv(out_dir / "sample_sales_eu.csv", index=False, sep=";", encoding="utf-8")
    print(f"Wrote {len(sales)} orders to {out_dir}/sample_sales.csv and sample_sales_eu.csv")
