"""One entry point for 'a user uploaded a CSV'.

    raw bytes -> clean DataFrame -> derived columns -> profile -> saved to disk

The DataFrame is stored as Parquet and the profile as JSON, both keyed by the
dataset id (a content hash). Uploading the same file twice reuses both.
In Phase 3 the Inngest worker loads them by id, which is why the event only
needs to carry `dataset_id`, never the data.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import settings
from core.schemas import DatasetProfile
from data_layer.loader import load_csv, load_dataset, make_dataset_id, save_dataset
from data_layer.profiler import add_derived_columns, profile_dataset


def profile_path(dataset_id: str) -> Path:
    return settings.data_dir / "datasets" / f"{dataset_id}.profile.json"


def save_profile(profile: DatasetProfile) -> None:
    path = profile_path(profile.dataset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")


def load_profile(dataset_id: str) -> DatasetProfile:
    return DatasetProfile.model_validate_json(profile_path(dataset_id).read_text(encoding="utf-8"))


def ingest(source: str | Path | bytes, use_cache: bool = True) -> tuple[pd.DataFrame, DatasetProfile]:
    raw = source if isinstance(source, bytes) else Path(source).read_bytes()
    dataset_id = make_dataset_id(raw)

    if use_cache and profile_path(dataset_id).exists():
        return load_dataset(dataset_id), load_profile(dataset_id)

    loaded = load_csv(raw)
    df, derive_notes = add_derived_columns(loaded.df)
    profile = profile_dataset(df, dataset_id, cleaning_notes=loaded.notes + derive_notes)

    save_dataset(df, dataset_id)
    save_profile(profile)
    return df, profile
