import pandas as pd
import pytest

from data_layer.ingest import ingest
from data_layer.loader import (clean_dataframe, load_csv, normalize_columns, normalize_name,
                               try_parse_dates, try_parse_numeric)


def text(values):
    return pd.Series(values, dtype="string")


@pytest.mark.parametrize("raw, expected", [
    ("Order Date", "order_date"),
    ("  Facturación (€) ", "facturacion"),
    ("Unit-Price", "unit_price"),
    ("Nº Pedido", "no_pedido"),
])
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


def test_duplicate_and_empty_column_names_are_made_unique():
    df = pd.DataFrame([[1, 2, 3]], columns=["Sales", "sales ", "€"])
    out, notes = normalize_columns(df)
    assert list(out.columns) == ["sales", "sales_2", "column_3"]
    assert notes


@pytest.mark.parametrize("values, expected", [
    (["$1,234.50", "$20.00", "(15.25)"], [1234.5, 20.0, -15.25]),     # US + negative
    (["1.234,56 €", "20,00 €", "3,5 €"], [1234.56, 20.0, 3.5]),        # European
    (["1 200", "300", "45"], [1200, 300, 45]),                         # space thousands
])
def test_numeric_parsing(values, expected):
    parsed, _ = try_parse_numeric(text(values), threshold=0.9)
    assert parsed.tolist() == pytest.approx(expected)


def test_integers_stay_integers():
    parsed, _ = try_parse_numeric(text(["1", "2", None]), threshold=0.9)
    assert str(parsed.dtype) == "Int64"


def test_codes_with_leading_zeros_stay_text():
    parsed, _ = try_parse_numeric(text(["00123", "04567", "08001"]), threshold=0.9)
    assert parsed is None


def test_mostly_text_column_is_not_numeric():
    parsed, _ = try_parse_numeric(text(["12", "abc", "def", "ghi"]), threshold=0.9)
    assert parsed is None


def test_iso_dates():
    parsed, _ = try_parse_dates(text(["2024-03-05", "2024-12-31"]), threshold=0.9)
    assert parsed.dt.month.tolist() == [3, 12]


def test_day_first_dates_are_detected_from_evidence():
    parsed, note = try_parse_dates(text(["05/03/2024", "25/12/2024"]), threshold=0.9)
    assert parsed.iloc[0] == pd.Timestamp("2024-03-05")
    assert "day/month/year" in note


def test_month_first_dates_are_detected_from_evidence():
    parsed, _ = try_parse_dates(text(["03/05/2024", "12/25/2024"]), threshold=0.9)
    assert parsed.iloc[0] == pd.Timestamp("2024-03-05")


def test_ambiguous_dates_are_reported():
    _, note = try_parse_dates(text(["03/05/2024", "04/06/2024"]), threshold=0.9)
    assert "ambiguous" in note


def test_product_names_are_not_dates():
    parsed, _ = try_parse_dates(text(["Monitor 27", "Laptop 15", "Desk"]), threshold=0.9)
    assert parsed is None


def test_clean_dataframe_end_to_end():
    raw = pd.DataFrame({
        "Fecha": ["01/02/2024", "15/02/2024", None],
        "Importe": ["1.000,50 €", "20,00 €", "5,00 €"],
        "Activo": ["Sí", "no", "si"],
        "Zip": ["08001", "08002", "08003"],
        "Region": [" North ", "South", ""],
    }).astype("string")
    df, notes = clean_dataframe(raw)
    assert pd.api.types.is_datetime64_any_dtype(df["fecha"])
    assert df["importe"].tolist() == pytest.approx([1000.5, 20.0, 5.0])
    assert df["activo"].tolist() == [True, False, True]
    assert df["zip"].tolist() == ["08001", "08002", "08003"]
    assert df["region"].tolist()[:2] == ["North", "South"]
    assert pd.isna(df["region"].iloc[2])
    assert any("European" in n for n in notes)


def test_load_csv_semicolon_and_latin1():
    raw = "Región;Ventas\nNorte;1.234,50\nSur;99,90\n".encode("cp1252")
    loaded = load_csv(raw)
    assert list(loaded.df.columns) == ["region", "ventas"]
    assert loaded.df["ventas"].tolist() == pytest.approx([1234.5, 99.9])
    assert any("delimiter" in n for n in loaded.notes)


def test_ingest_saves_and_reuses_cache(tmp_settings):
    raw = b"date,sales\n2024-01-01,10\n2024-01-02,20\n"
    df1, profile1 = ingest(raw)
    df2, profile2 = ingest(raw)
    assert profile1.dataset_id == profile2.dataset_id
    assert (tmp_settings.data_dir / "datasets" / f"{profile1.dataset_id}.parquet").exists()
    pd.testing.assert_frame_equal(df1, df2)
    assert pd.api.types.is_datetime64_any_dtype(df2["date"])
