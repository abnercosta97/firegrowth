"""Preparação de dados e execução do benchmark mínimo."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from shapely import from_wkt, to_wkt
from shapely.ops import transform, unary_union

from .data import read_table, validate_release
from .geometry import _TO_EQUAL_AREA
from .metrics import regression_metrics
from .splits import temporal_split


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    """Write Parquet through DuckDB so pyarrow is not required."""
    import duckdb

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(database=":memory:")
    connection.register("frame", frame)
    connection.execute("COPY frame TO ? (FORMAT PARQUET)", [str(path)])
    connection.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_event_daily(dataset_root: str | Path, output_root: str | Path) -> dict[str, object]:
    """Build one row per observed event-day with cumulative union area."""
    started = time.perf_counter()
    root = Path(dataset_root)
    out = Path(output_root)
    validation = validate_release(root)
    if not validation["valid"]:
        raise ValueError(validation["errors"])
    fronts = read_table(root, "fronts")
    fronts["observation_date"] = pd.to_datetime(fronts["observation_date_utc"]).dt.normalize()
    fronts = fronts.sort_values(["event_id", "observation_date", "front_id"])
    rows: list[dict[str, object]] = []
    for (event_id, day), group in fronts.groupby(["event_id", "observation_date"], sort=False):
        geometries = [from_wkt(value) for value in group["geometry"] if value]
        if not geometries:
            continue
        daily_union = unary_union(geometries)
        previous = (
            rows[-1]["_cumulative_geometry"] if rows and rows[-1]["event_id"] == event_id else None
        )
        cumulative = daily_union if previous is None else unary_union([previous, daily_union])
        projected = transform(_TO_EQUAL_AREA, cumulative)
        rows.append(
            {
                "event_id": event_id,
                "observation_date": day.date(),
                "front_count": int(len(group)),
                "daily_union_wkt": to_wkt(daily_union, rounding_precision=8),
                "cumulative_area_ha": float(projected.area / 10_000),
                "has_front": True,
                "_cumulative_geometry": cumulative,
            }
        )
    daily = pd.DataFrame(rows)
    if daily.empty:
        raise ValueError("no valid front geometries were found")
    daily = daily.drop(columns=["_cumulative_geometry"])
    _write_parquet(daily, out / "event_daily.parquet")
    manifest = {
        "input": str(root),
        "rows": int(len(daily)),
        "events": int(daily["event_id"].nunique()),
        "date_min": str(daily["observation_date"].min()),
        "date_max": str(daily["observation_date"].max()),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    (out / "prepare_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build_supervised(
    event_daily: pd.DataFrame, coverage: pd.DataFrame, horizon_days: int
) -> pd.DataFrame:
    """Create leakage-safe rows only when the exact future date is observed."""
    work = event_daily.copy()
    work["reference_date"] = pd.to_datetime(work["observation_date"]).dt.normalize()
    work = work.sort_values(["event_id", "reference_date"])
    work["growth_ha_day"] = work.groupby("event_id", sort=False)["cumulative_area_ha"].diff()
    work["last_growth_ha_day"] = work.groupby("event_id", sort=False)["growth_ha_day"].shift(1)
    work["moving_average_growth_ha_day"] = work.groupby("event_id", sort=False)[
        "growth_ha_day"
    ].transform(lambda values: values.shift(1).rolling(3, min_periods=1).mean())
    target = work[["event_id", "reference_date", "cumulative_area_ha"]].rename(
        columns={"reference_date": "target_date", "cumulative_area_ha": "target_area_ha"}
    )
    target["reference_date"] = target["target_date"] - pd.Timedelta(days=horizon_days)
    target = target.rename(columns={"target_date": "future_observation_date"})
    result = work.merge(target, on=["event_id", "reference_date"], how="left")
    result["horizon_days"] = horizon_days
    result["target_end"] = result["future_observation_date"]
    result["target_growth_ha_day"] = (
        result["target_area_ha"] - result["cumulative_area_ha"]
    ) / horizon_days
    valid_coverage = set(
        pd.to_datetime(
            coverage.loc[
                coverage["processing_complete"] & coverage["observation_available"], "date_utc"
            ]
        ).dt.normalize()
    )
    result["reference_covered"] = result["reference_date"].isin(valid_coverage)
    result["target_covered"] = result["future_observation_date"].isin(valid_coverage)
    result["eligible"] = (
        result["target_growth_ha_day"].notna()
        & result["reference_covered"]
        & result["target_covered"]
    )
    result["eligibility_reason"] = np.where(
        result["eligible"],
        "complete_exact_future_observation",
        "missing_exact_future_observation_or_coverage",
    )
    return result.drop(columns=["target_area_ha", "future_observation_date"])


def run_benchmark(
    dataset_root: str | Path, output_root: str | Path, horizons: list[int]
) -> dict[str, object]:
    """Prepare supervised tables, run baselines and write a reproducible report."""
    root, out = Path(dataset_root), Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    daily_path = out / "event_daily.parquet"
    if not daily_path.exists():
        prepare_event_daily(root, out)
    import duckdb

    connection = duckdb.connect(database=":memory:")
    daily = connection.execute("SELECT * FROM read_parquet(?)", [str(daily_path)]).fetchdf()
    coverage = read_table(root, "coverage")
    all_metrics: list[dict[str, object]] = []
    all_predictions: list[pd.DataFrame] = []
    all_exclusions: list[pd.DataFrame] = []
    for horizon in horizons:
        supervised = build_supervised(daily, coverage, horizon)
        _write_parquet(supervised, out / f"supervised_h{horizon}.parquet")
        all_exclusions.append(
            supervised.loc[
                ~supervised["eligible"],
                ["event_id", "reference_date", "horizon_days", "eligibility_reason"],
            ]
        )
        partitions = temporal_split(supervised, target_end_column="target_end")
        boundary_excluded = partitions["excluded"].copy()
        if not boundary_excluded.empty:
            boundary_excluded["eligibility_reason"] = "event_crosses_temporal_partition"
            all_exclusions.append(
                boundary_excluded[
                    ["event_id", "reference_date", "horizon_days", "eligibility_reason"]
                ]
            )
        for name, part in partitions.items():
            if name == "excluded" or part.empty:
                continue
            # The leaderboard must compare all models on the same cases.  A
            # missing history value therefore excludes the row from the common
            # cohort rather than silently giving each model a different n.
            eligible = part.loc[
                part["eligible"]
                & part["last_growth_ha_day"].notna()
                & part["moving_average_growth_ha_day"].notna()
            ].copy()
            for model in ("zero", "last_value", "moving_average"):
                if model == "zero":
                    prediction = np.zeros(len(eligible), dtype=float)
                else:
                    column = (
                        "last_growth_ha_day"
                        if model == "last_value"
                        else "moving_average_growth_ha_day"
                    )
                    prediction = eligible[column].to_numpy(float)
                scores = regression_metrics(
                    eligible["target_growth_ha_day"].to_numpy(float), prediction
                )
                all_metrics.append(
                    {"horizon_days": horizon, "partition": name, "model": model, **scores}
                )
                all_predictions.append(
                    pd.DataFrame(
                        {
                            "event_id": eligible["event_id"].to_numpy(),
                            "reference_date": eligible["reference_date"].dt.date,
                            "horizon_days": horizon,
                            "partition": name,
                            "model": model,
                            "observed_growth_ha_day": eligible["target_growth_ha_day"].to_numpy(
                                float
                            ),
                            "predicted_growth_ha_day": prediction,
                        }
                    )
                )
    metrics = pd.DataFrame(all_metrics)
    predictions = (
        pd.concat(all_predictions, ignore_index=True) if all_predictions else pd.DataFrame()
    )
    _write_parquet(predictions, out / "predictions.parquet")
    metrics.to_csv(out / "metrics.csv", index=False)
    _write_parquet(pd.concat(all_exclusions, ignore_index=True), out / "exclusions.parquet")
    manifest = {
        "dataset_root": str(root),
        "horizons_days": horizons,
        "dataset_revision": "v1.0.0",
        "dataset_commit": "9b5a8f1dae609b1f00fee55b99bf27be969bf737",
        "event_daily_sha256": _sha256(daily_path),
        "prediction_rows": int(len(predictions)),
        "metrics_rows": int(len(metrics)),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_config(path: str | Path) -> dict[str, object]:
    """Load a YAML benchmark configuration."""
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
