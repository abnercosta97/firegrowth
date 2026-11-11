"""Leitura e validação do dataset MATOPIBA."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

REQUIRED = {
    "events": {"event_id", "date_min_utc", "geometry"},
    "fronts": {"front_id", "event_id", "observation_date_utc", "geometry"},
    "coverage": {"date_utc", "processing_complete", "observation_available"},
}


def read_table(root: str | Path, name: str) -> pd.DataFrame:
    """Read one release table from a local dataset directory."""
    path = Path(root) / "data" / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    return duckdb.connect(database=":memory:").execute(
        "SELECT * FROM read_parquet(?)", [str(path)]
    ).fetchdf()


def validate_release(root: str | Path) -> dict[str, object]:
    """Validate required tables, keys and front-to-event referential integrity."""
    tables = {name: read_table(root, name) for name in REQUIRED}
    errors: list[str] = []
    for name, columns in REQUIRED.items():
        missing = columns - set(tables[name].columns)
        if missing:
            errors.append(f"{name}: missing columns {sorted(missing)}")
    if not errors:
        events = tables["events"]
        fronts = tables["fronts"]
        if events["event_id"].isna().any() or events["event_id"].duplicated().any():
            errors.append("events.event_id must be unique and non-null")
        orphan = ~fronts["event_id"].isin(events["event_id"])
        if orphan.any():
            errors.append(f"fronts contains {int(orphan.sum())} orphan rows")
    return {
        "valid": not errors,
        "errors": errors,
        "rows": {name: int(table.shape[0]) for name, table in tables.items()},
    }
