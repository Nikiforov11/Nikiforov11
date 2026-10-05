"""Load any sales CSV and turn it into a clean, typed DataFrame.

Real-world CSVs are messy: semicolon separators, Latin-1 encodings,
'1.234,56 €' amounts, '05/03/2024' dates, 'Facturación ' headers...
We read every column as text first, then decide the type ourselves.
That is more predictable than letting pandas guess, and it lets us
write down every decision in `notes` so the user (and the LLM) can see it.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from core.config import settings

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")
DELIMITERS = ",;\t|"

_CURRENCY_SYMBOLS_RE = r"[€$£¥₹]"
# Symbols + spaces + a literal non-breaking space (pyarrow regexes reject "\\u" escapes).
_CURRENCY_RE = r"[€$£¥₹\s" + "\u00a0" + "]"
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}")
_DMY_RE = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})")
_BOOL_VALUES = {"true": True, "false": False, "yes": True, "no": False,
                "y": True, "n": False, "si": True, "sí": True}


@dataclass
class LoadedDataset:
    df: pd.DataFrame
    dataset_id: str
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def make_dataset_id(raw: bytes) -> str:
    """Content hash: the same file always gets the same id, which gives us
    free caching of its profile later on."""
    return hashlib.sha1(raw).hexdigest()[:12]


def _decode(raw: bytes) -> tuple[str, str]:
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode the file with any supported encoding")


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
    except csv.Error:
        return ","


def read_csv_bytes(raw: bytes) -> tuple[pd.DataFrame, list[str]]:
    text, encoding = _decode(raw)
    delimiter = _sniff_delimiter(text)
    df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str,
                     skipinitialspace=True, keep_default_na=True)
    notes = []
    if encoding != "utf-8-sig":
        notes.append(f"File decoded as {encoding}.")
    if delimiter != ",":
        notes.append(f"Detected delimiter {delimiter!r}.")
    return df, notes


def load_csv(source: str | Path | bytes) -> LoadedDataset:
    raw = source if isinstance(source, bytes) else Path(source).read_bytes()
    df, notes = read_csv_bytes(raw)
    df, clean_notes = clean_dataframe(df)
    return LoadedDataset(df=df, dataset_id=make_dataset_id(raw), notes=notes + clean_notes)


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def normalize_name(name: str) -> str:
    """'Facturación (€)' -> 'facturacion'. ASCII snake_case is easier for the
    LLM to reproduce exactly, which means fewer 'column not found' errors."""
    name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip().lower())
    return name.strip("_")


def normalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    new_names: list[str] = []
    seen: dict[str, int] = {}
    for i, col in enumerate(df.columns):
        base = normalize_name(col) or f"column_{i + 1}"
        if base in seen:
            seen[base] += 1
            base = f"{base}_{seen[base]}"
        else:
            seen[base] = 1
        new_names.append(base)

    renamed = {old: new for old, new in zip(df.columns, new_names) if old != new}
    notes = []
    if renamed:
        pairs = ", ".join(f"'{o}' -> '{n}'" for o, n in list(renamed.items())[:8])
        more = f" (+{len(renamed) - 8} more)" if len(renamed) > 8 else ""
        notes.append(f"Renamed columns: {pairs}{more}.")
    out = df.copy()
    out.columns = new_names
    return out, notes


def _is_text(s: pd.Series) -> bool:
    # pandas 3 uses a dedicated 'str' dtype, pandas 2 uses object.
    return pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)


def _parse_rate(parsed: pd.Series, original: pd.Series) -> float:
    n = original.notna().sum()
    return 0.0 if n == 0 else parsed.notna().sum() / n


def try_parse_bool(s: pd.Series) -> pd.Series | None:
    values = s.dropna().str.lower()
    if values.empty or not set(values.unique()) <= set(_BOOL_VALUES):
        return None
    return s.str.lower().map(_BOOL_VALUES).astype("boolean")


def try_parse_numeric(s: pd.Series, threshold: float) -> tuple[pd.Series | None, str | None]:
    """Parse amounts like '$1,234.50', '1.234,50 €', '(120)', '15%'.

    Returns (parsed_series, note) or (None, None) if the column isn't numeric.
    """
    values = s.dropna()
    if values.empty:
        return None, None
    # Codes with leading zeros (zip codes, '00123' ids) must stay text.
    if values.str.match(r"^0\d").mean() > 0.1:
        return None, None

    cleaned = s.str.replace(_CURRENCY_RE, "", regex=True)
    cleaned = cleaned.str.replace(r"^\((.*)\)$", r"-\1", regex=True)   # (120) -> -120
    had_percent = cleaned.str.endswith("%").fillna(False).any()
    cleaned = cleaned.str.rstrip("%")

    # Decide between 1,234.56 (US) and 1.234,56 (EU) from evidence in the data.
    sample = cleaned.dropna()
    eu_evidence = sample.str.contains(r",\d{1,2}$|\.\d{3},", regex=True).sum()
    us_evidence = sample.str.contains(r"\.\d{1,2}$|,\d{3}\.", regex=True).sum()
    if eu_evidence > us_evidence:
        candidate = cleaned.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        style = "European (1.234,56)"
    else:
        candidate = cleaned.str.replace(",", "", regex=False)
        style = None

    parsed = pd.to_numeric(candidate, errors="coerce")
    if _parse_rate(parsed, s) < threshold:
        return None, None

    # Keep integers as integers (nullable Int64 handles missing values).
    if parsed.dropna().mod(1).eq(0).all():
        parsed = parsed.astype("Int64")
    else:
        parsed = parsed.astype("float64")

    details = []
    if style:
        details.append(f"{style} number format")
    if had_percent:
        details.append("'%' signs removed, values kept as written")
    if s.str.contains(_CURRENCY_SYMBOLS_RE, regex=True).fillna(False).any():
        details.append("currency symbols removed")
    note = ", ".join(details) if details else None
    return parsed, note


def _detect_dayfirst(values: pd.Series) -> tuple[bool, bool]:
    """Return (dayfirst, ambiguous) for d/m/y-looking strings."""
    parts = values.str.extract(_DMY_RE).dropna().astype(int)
    if parts.empty:
        return settings.date_dayfirst_default, True
    if (parts[0] > 12).any():
        return True, False
    if (parts[1] > 12).any():
        return False, False
    return settings.date_dayfirst_default, True


def try_parse_dates(s: pd.Series, threshold: float) -> tuple[pd.Series | None, str | None]:
    values = s.dropna()
    # Cheap pre-check: dates contain digits and are at least 6 chars long.
    if values.empty or not (values.str.len().ge(6) & values.str.contains(r"\d")).mean() >= threshold:
        return None, None

    note = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            if values.str.match(_ISO_DATE_RE).mean() >= threshold:
                parsed = pd.to_datetime(s, format="ISO8601", errors="coerce")
            elif values.str.match(_DMY_RE).mean() >= threshold:
                dayfirst, ambiguous = _detect_dayfirst(values)
                parsed = pd.to_datetime(s, format="mixed", dayfirst=dayfirst, errors="coerce")
                order = "day/month/year" if dayfirst else "month/day/year"
                note = (f"dates are ambiguous, assumed {order} (set DATE_DAYFIRST to change)"
                        if ambiguous else f"read as {order}")
            else:
                parsed = pd.to_datetime(s, format="mixed", errors="coerce")
        except (ValueError, TypeError):
            # Typically mixed timezone offsets: normalise everything to UTC.
            parsed = pd.to_datetime(s, format="mixed", errors="coerce", utc=True)

    if _parse_rate(parsed, s) < threshold:
        return None, None
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_convert(None)
    return parsed, note


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    threshold = settings.parse_threshold
    df, notes = normalize_columns(df)

    # Drop rows and columns that are completely empty.
    before = df.shape
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.shape != before:
        notes.append(f"Dropped {before[0] - df.shape[0]} empty rows "
                     f"and {before[1] - df.shape[1]} empty columns.")

    df = df.copy()
    for col in df.columns:
        s = df[col]
        if not _is_text(s):
            continue
        s = s.str.strip().replace("", pd.NA)
        df[col] = s

        if (parsed := try_parse_bool(s)) is not None:
            df[col] = parsed
            notes.append(f"'{col}' converted to yes/no values.")
            continue

        parsed, note = try_parse_numeric(s, threshold)
        if parsed is not None:
            df[col] = parsed
            if note:
                notes.append(f"'{col}' converted to numbers: {note}.")
            _note_failures(notes, col, s, parsed)
            continue

        parsed, note = try_parse_dates(s, threshold)
        if parsed is not None:
            df[col] = parsed
            notes.append(f"'{col}' converted to dates" + (f": {note}." if note else "."))
            _note_failures(notes, col, s, parsed)

    df = df.reset_index(drop=True)
    return df, notes


def _note_failures(notes: list[str], col: str, original: pd.Series, parsed: pd.Series) -> None:
    failed = int(original.notna().sum() - parsed.notna().sum())
    if failed:
        notes.append(f"'{col}': {failed} value(s) could not be converted and were set to empty.")


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
def _dataset_path(dataset_id: str) -> Path:
    return settings.data_dir / "datasets" / f"{dataset_id}.parquet"


def save_dataset(df: pd.DataFrame, dataset_id: str) -> Path:
    """Parquet keeps the dtypes we worked to infer (dates stay dates),
    and loads far faster than re-parsing the CSV on every question."""
    path = _dataset_path(dataset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def load_dataset(dataset_id: str) -> pd.DataFrame:
    path = _dataset_path(dataset_id)
    if not path.exists():
        raise FileNotFoundError(f"No stored dataset with id '{dataset_id}'")
    return pd.read_parquet(path)
