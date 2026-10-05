"""Build a compact description of a dataset (the 'profile').

The profile is what the LLM sees instead of the data itself. It answers:
which columns exist, what type they are, what they *mean* (role), and what
values they hold. A good profile is the single biggest factor in answer
quality, and it costs tokens on every question, so it has to stay compact.

Role detection here is heuristic (column names in English, Spanish and a
bit of Catalan). In a later phase the LLM double-checks it once per upload
and the user can correct it in the UI.
"""
from __future__ import annotations

import pandas as pd

from core.schemas import ColumnKind, ColumnProfile, ColumnRole, DatasetProfile
from core.utils import to_jsonable

SAMPLE_ROWS = 3
TOP_VALUES = 5

# Order matters: the first matching role wins.
NUMERIC_ROLE_KEYWORDS: list[tuple[ColumnRole, set[str]]] = [
    (ColumnRole.PROFIT, {"profit", "margin", "beneficio", "ganancia", "benefici"}),
    (ColumnRole.DISCOUNT, {"discount", "descuento", "descompte"}),
    (ColumnRole.COST, {"cost", "coste", "costo", "cogs", "cost_price"}),
    (ColumnRole.PRICE, {"price", "precio", "preu", "pvp", "rate"}),
    (ColumnRole.QUANTITY, {"qty", "quantity", "units", "unit", "cantidad", "unidades", "quantitat", "volume"}),
    (ColumnRole.REVENUE, {"revenue", "sales", "sale", "amount", "total", "turnover", "importe", "ventas",
                          "venta", "facturacion", "ingresos", "vendes", "gross", "net", "income", "value"}),
]
ENTITY_ROLE_KEYWORDS: list[tuple[ColumnRole, set[str]]] = [
    (ColumnRole.CATEGORY, {"category", "categoria", "segment", "segmento", "type", "tipo", "family",
                           "familia", "department", "departamento", "class", "brand", "marca"}),
    (ColumnRole.CUSTOMER, {"customer", "client", "cliente", "buyer", "comprador", "account"}),
    (ColumnRole.PRODUCT, {"product", "producto", "producte", "item", "articulo", "article", "sku", "model"}),
    (ColumnRole.CHANNEL, {"channel", "canal", "source", "platform"}),
    (ColumnRole.REGION, {"region", "country", "pais", "city", "ciudad", "ciutat", "state", "province",
                         "provincia", "store", "tienda", "botiga", "branch", "location", "zone", "zona",
                         "market", "territory", "comunidad"}),
]
ID_TOKENS = {"id", "uuid", "ref"}
ID_SUFFIXES = ("_number", "_no", "_num", "_code")
ID_HINTS = {"invoice", "order", "transaction", "ticket", "factura", "pedido"}
PREFERRED_DATE_WORDS = {"order", "sale", "sales", "invoice", "transaction", "purchase", "fecha", "date"}
SECONDARY_DATE_WORDS = {"ship", "shipping", "delivery", "due", "return", "envio", "entrega"}


def _matches(name: str, keywords: set[str]) -> bool:
    tokens = set(name.split("_"))
    return any(kw in tokens or (len(kw) >= 5 and kw in name) for kw in keywords)


def _looks_like_id(name: str, s: pd.Series) -> bool:
    if set(name.split("_")) & ID_TOKENS or name.endswith(ID_SUFFIXES):
        return True
    # 'order', 'invoice'... only mean "identifier" when values are mostly unique
    # ('order_status' is a category, 'order' with 10k distinct values is an id).
    non_null = max(int(s.notna().sum()), 1)
    return _matches(name, ID_HINTS) and s.nunique() / non_null > 0.5


# --------------------------------------------------------------------------- #
# Column level
# --------------------------------------------------------------------------- #
def detect_kind(s: pd.Series) -> ColumnKind:
    if pd.api.types.is_bool_dtype(s):
        return ColumnKind.BOOLEAN
    if pd.api.types.is_datetime64_any_dtype(s):
        return ColumnKind.DATETIME
    if pd.api.types.is_numeric_dtype(s):
        return ColumnKind.NUMERIC
    non_null = s.notna().sum()
    unique = s.nunique()
    if unique <= 50 or (non_null and unique / non_null <= 0.2):
        return ColumnKind.CATEGORICAL
    return ColumnKind.TEXT


def detect_role(name: str, s: pd.Series, kind: ColumnKind) -> ColumnRole:
    if kind == ColumnKind.DATETIME:
        return ColumnRole.DATE
    if kind == ColumnKind.NUMERIC:
        for role, words in NUMERIC_ROLE_KEYWORDS:
            if _matches(name, words):
                return role
    for role, words in ENTITY_ROLE_KEYWORDS:
        if _matches(name, words):
            return role
    if _looks_like_id(name, s):
        return ColumnRole.ID
    # A text column where (almost) every value is different behaves like an id.
    if kind == ColumnKind.TEXT and s.nunique() >= 0.95 * max(s.notna().sum(), 1):
        return ColumnRole.ID
    return ColumnRole.OTHER


def profile_column(name: str, s: pd.Series) -> ColumnProfile:
    kind = detect_kind(s)
    profile = ColumnProfile(
        name=name,
        dtype=str(s.dtype),
        kind=kind,
        role=detect_role(name, s, kind),
        missing=int(s.isna().sum()),
        unique=int(s.nunique()),
    )
    values = s.dropna()
    if values.empty:
        return profile

    if kind == ColumnKind.NUMERIC:
        profile.min = to_jsonable(values.min())
        profile.max = to_jsonable(values.max())
        profile.mean = to_jsonable(values.mean())
        profile.median = to_jsonable(values.median())
    elif kind == ColumnKind.DATETIME:
        profile.date_min = to_jsonable(values.min())
        profile.date_max = to_jsonable(values.max())
    elif kind in (ColumnKind.CATEGORICAL, ColumnKind.TEXT, ColumnKind.BOOLEAN):
        counts = values.astype(str).value_counts().head(TOP_VALUES)
        profile.top_values = {str(k): int(v) for k, v in counts.items()}
    return profile


# --------------------------------------------------------------------------- #
# Dataset level
# --------------------------------------------------------------------------- #
def _pick_primary_date(df: pd.DataFrame, cols: list[ColumnProfile]) -> str | None:
    candidates = [c.name for c in cols if c.role == ColumnRole.DATE]
    if not candidates:
        return None

    def score(name: str) -> tuple[int, int]:
        preferred = int(_matches(name, PREFERRED_DATE_WORDS))
        secondary = int(_matches(name, SECONDARY_DATE_WORDS))
        return (preferred - secondary, int(df[name].notna().sum()))

    return max(candidates, key=score)


def _pick_primary_metric(df: pd.DataFrame, cols: list[ColumnProfile]) -> str | None:
    candidates = [c.name for c in cols if c.role == ColumnRole.REVENUE]
    if not candidates:
        return None
    strong = {"revenue", "sales", "importe", "ventas", "facturacion", "vendes", "turnover"}
    # Prefer explicit revenue words, then the column with the biggest total
    # (usually the line total rather than a unit value).
    return max(candidates, key=lambda n: (int(_matches(n, strong)), float(df[n].sum())))


def add_derived_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """If there is no revenue column but there are price and quantity,
    create revenue = price * quantity so 'total sales' questions still work."""
    cols = [profile_column(c, df[c]) for c in df.columns]
    roles = {c.role for c in cols}
    if ColumnRole.REVENUE in roles:
        return df, []
    price = next((c.name for c in cols if c.role == ColumnRole.PRICE), None)
    qty = next((c.name for c in cols if c.role == ColumnRole.QUANTITY), None)
    if not (price and qty) or "revenue" in df.columns:
        return df, []
    out = df.copy()
    out["revenue"] = out[price].astype("float64") * out[qty].astype("float64")
    return out, [f"Added column 'revenue' = {price} * {qty} (no revenue column found)."]


def profile_dataset(df: pd.DataFrame, dataset_id: str,
                    cleaning_notes: list[str] | None = None) -> DatasetProfile:
    cols = [profile_column(c, df[c]) for c in df.columns]
    n_sample = min(SAMPLE_ROWS, len(df))
    # Fixed random_state: the same file always produces the same profile,
    # so prompts are reproducible and cacheable.
    sample = df.sample(n_sample, random_state=42) if n_sample else df.head(0)
    return DatasetProfile(
        dataset_id=dataset_id,
        rows=len(df),
        columns=df.shape[1],
        column_profiles=cols,
        sample_rows=to_jsonable(sample.to_dict(orient="records")),
        primary_date=_pick_primary_date(df, cols),
        primary_metric=_pick_primary_metric(df, cols),
        cleaning_notes=cleaning_notes or [],
    )


# --------------------------------------------------------------------------- #
# Prompt context
# --------------------------------------------------------------------------- #
def _describe_column(c: ColumnProfile) -> str:
    role = f", role={c.role.value}" if c.role != ColumnRole.OTHER else ""
    parts = [f"- {c.name} [{c.kind.value}{role}]"]
    if c.kind == ColumnKind.NUMERIC and c.min is not None:
        parts.append(f"min {c.min:g}, max {c.max:g}, mean {c.mean:g}")
    elif c.kind == ColumnKind.DATETIME and c.date_min:
        parts.append(f"{c.date_min} to {c.date_max}")
    elif c.role == ColumnRole.ID and c.top_values:
        parts.append(f"{c.unique} distinct, e.g. {next(iter(c.top_values))}")
    elif c.top_values:
        top = ", ".join(f"{k} ({v})" for k, v in c.top_values.items())
        label = "values" if c.unique <= TOP_VALUES else f"{c.unique} values, top"
        parts.append(f"{label}: {top}")
    if c.missing:
        parts.append(f"{c.missing} missing")
    return " ".join(parts[:1]) + (" " + "; ".join(parts[1:]) if len(parts) > 1 else "")


def to_prompt_context(profile: DatasetProfile) -> str:
    """Compact, LLM-friendly text version of the profile (used from Phase 2)."""
    lines = [f"Dataset: {profile.rows:,} rows x {profile.columns} columns"]
    if profile.primary_date:
        lines.append(f"Main date column: {profile.primary_date}")
    if profile.primary_metric:
        lines.append(f"Main sales value column: {profile.primary_metric}")
    lines.append("Columns:")
    lines.extend(_describe_column(c) for c in profile.column_profiles)
    if profile.sample_rows:
        lines.append("Sample rows:")
        lines.extend(f"  {row}" for row in profile.sample_rows)
    if profile.cleaning_notes:
        lines.append("Data preparation notes:")
        lines.extend(f"  {n}" for n in profile.cleaning_notes)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# User corrections
# --------------------------------------------------------------------------- #
def apply_overrides(profile: DatasetProfile, roles: dict[str, ColumnRole | str] | None = None,
                    primary_date: str | None = None,
                    primary_metric: str | None = None) -> DatasetProfile:
    """Return a copy of the profile with the user's corrections applied.
    Heuristics get roles wrong sometimes; the UI lets the user fix them, and
    the corrected profile is what the agent sees from then on."""
    updated = profile.model_copy(deep=True)
    for col in updated.column_profiles:
        if roles and col.name in roles:
            col.role = ColumnRole(roles[col.name])
    names = {c.name for c in updated.column_profiles}
    if primary_date is not None:
        updated.primary_date = primary_date if primary_date in names else None
    if primary_metric is not None:
        updated.primary_metric = primary_metric if primary_metric in names else None
    return updated
