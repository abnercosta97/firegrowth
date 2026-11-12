"""Análise derivada de eventos com múltiplas datas observadas."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import _read_parquet, _write_csv, build_event_summary
from .data import read_table, validate_release
from .pipeline import _write_parquet, build_supervised
from .splits import temporal_split


def _duration_bin(values: pd.Series) -> pd.Series:
    return pd.cut(
        values,
        bins=[0, 1, 2, 3, 7, 14, 30, 60, 90, np.inf],
        labels=["1", "2", "3", "4–7", "8–14", "15–30", "31–60", "61–90", ">90"],
        include_lowest=True,
    ).astype(str)


def _plots(summary: pd.DataFrame, targets: pd.DataFrame, report: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = report / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    for column, filename, title in [
        ("duration_bin", "multiday_duration_bins.png", "Eventos multidiários por duração"),
        ("type_label", "multiday_types.png", "Eventos multidiários por tipo"),
    ]:
        counts = summary[column].value_counts().sort_index()
        fig, ax = plt.subplots(figsize=(8, 4))
        counts.plot(kind="bar", ax=ax)
        ax.set(title=title, xlabel=column, ylabel="Eventos")
        fig.tight_layout()
        fig.savefig(figures / filename, dpi=160)
        plt.close(fig)
    counts = targets.groupby("horizon_days")[
        ["history_target", "history2_target", "consecutive_target"]
    ].sum()
    fig, ax = plt.subplots(figsize=(8, 4))
    counts.plot(kind="bar", ax=ax)
    ax.set(title="Coortes elegíveis por horizonte", xlabel="Horizonte (dias)", ylabel="Referências")
    fig.tight_layout()
    fig.savefig(figures / "multiday_cohort_sizes.png", dpi=160)
    plt.close(fig)


def run_multiday_analysis(
    dataset_root: str | Path, benchmark_root: str | Path, report_root: str | Path
) -> dict[str, object]:
    """Generate the multiday cohort, targets, statistics and figures."""
    root, benchmark, report = Path(dataset_root), Path(benchmark_root), Path(report_root)
    report.mkdir(parents=True, exist_ok=True)
    validation = validate_release(root)
    if not validation["valid"]:
        raise ValueError(validation["errors"])
    events = read_table(root, "events")
    fronts = read_table(root, "fronts")
    sensors = read_table(root, "front_sensors")
    coverage = read_table(root, "coverage")
    event_daily = _read_parquet(benchmark / "event_daily.parquet")
    summary = build_event_summary(events, fronts, sensors, event_daily)
    summary["duration_bin"] = _duration_bin(summary["observed_span_days"])
    summary["cohort_multiday"] = summary["observed_days"] >= 2
    multiday_ids = set(summary.loc[summary["cohort_multiday"], "event_id"])
    multiday_summary = summary.loc[summary["cohort_multiday"]].copy()
    multiday_daily = event_daily.loc[event_daily["event_id"].isin(multiday_ids)].copy()
    _write_parquet(multiday_summary, report / "multiday_event_summary.parquet")
    _write_parquet(multiday_daily, report / "multiday_event_daily.parquet")

    base = event_daily.copy()
    base["reference_date"] = pd.to_datetime(base["observation_date"]).dt.normalize()
    base = base.sort_values(["event_id", "reference_date"])
    base["gap_before_reference_days"] = base.groupby("event_id")["reference_date"].diff().dt.days
    base["prior_observation_count"] = base.groupby("event_id").cumcount()
    base["has_previous_observation"] = base["prior_observation_count"] >= 1
    base["consecutive_history"] = base["gap_before_reference_days"].eq(1)
    history = base[
        [
            "event_id",
            "reference_date",
            "gap_before_reference_days",
            "prior_observation_count",
            "has_previous_observation",
            "consecutive_history",
        ]
    ]
    target_rows = []
    for horizon in (1, 3):
        target = build_supervised(event_daily, coverage, horizon)
        target = target.merge(history, on=["event_id", "reference_date"], how="left")
        target["history_target"] = target["eligible"] & target["has_previous_observation"]
        target["history2_target"] = target["eligible"] & (target["prior_observation_count"] >= 2)
        target["consecutive_target"] = target["eligible"] & target["consecutive_history"]
        parts = temporal_split(target, target_end_column="target_end")
        target["partition"] = "excluded_boundary"
        for name in ("train", "validation", "test"):
            target.loc[parts[name].index, "partition"] = name
        target_rows.append(target)
    targets = pd.concat(target_rows, ignore_index=True)
    _write_parquet(targets, report / "multiday_growth_targets.parquet")
    membership_columns = [
        "event_id",
        "reference_date",
        "horizon_days",
        "partition",
        "prior_observation_count",
        "gap_before_reference_days",
        "history_target",
        "history2_target",
        "consecutive_target",
        "eligible",
        "eligibility_reason",
    ]
    _write_parquet(targets[membership_columns], report / "cohort_membership.parquet")

    _write_csv(
        multiday_summary.groupby(["type_code", "type_label"], dropna=False)
        .agg(
            events=("event_id", "nunique"),
            mean_duration_days=("observed_span_days", "mean"),
            median_duration_days=("observed_span_days", "median"),
            mean_fronts=("front_count", "mean"),
            median_fronts=("front_count", "median"),
            median_initial_area_ha=("initial_area_ha", "median"),
            median_final_area_ha=("final_area_ha", "median"),
        )
        .reset_index(),
        report / "multiday_type_statistics.csv",
    )
    _write_csv(
        multiday_summary.groupby("duration_bin", dropna=False)
        .agg(
            events=("event_id", "nunique"),
            mean_duration_days=("observed_span_days", "mean"),
            median_duration_days=("observed_span_days", "median"),
            mean_fronts=("front_count", "mean"),
            median_final_area_ha=("final_area_ha", "median"),
        )
        .reset_index(),
        report / "multiday_duration_statistics.csv",
    )
    _write_csv(
        multiday_summary.groupby(["type_label", "duration_bin"], dropna=False)
        .size()
        .rename("events")
        .reset_index(),
        report / "multiday_type_duration_statistics.csv",
    )
    _write_csv(
        targets.groupby(["horizon_days", "partition"])
        .agg(
            references=("event_id", "size"),
            events=("event_id", "nunique"),
            history_target=("history_target", "sum"),
            history2_target=("history2_target", "sum"),
            consecutive_target=("consecutive_target", "sum"),
        )
        .reset_index(),
        report / "multiday_partition_statistics.csv",
    )
    _write_csv(
        multiday_summary.groupby("max_gap_days", dropna=False)
        .size()
        .rename("events")
        .reset_index(),
        report / "multiday_gap_statistics.csv",
    )
    _plots(multiday_summary, targets, report)
    quality = {
        "dataset_revision": "v1.0.0",
        "dataset_commit": "9b5a8f1dae609b1f00fee55b99bf27be969bf737",
        "all_events": int(len(summary)),
        "multiday_events": int(len(multiday_summary)),
        "single_observation_events": int((summary["observed_days"] == 1).sum()),
        "multiday_fraction": float(len(multiday_summary) / len(summary)),
        "event_daily_rows_multiday": int(len(multiday_daily)),
        "meteorology_included": False,
        "selection_rule": "observed_days >= 2; derived from fronts, not final duration",
    }
    (report / "multiday_quality_report.json").write_text(
        json.dumps(quality, indent=2, default=str), encoding="utf-8"
    )
    (report / "README.md").write_text(
        "\n".join(
            [
                "# Análise da coorte multidiária",
                "",
                "Coorte retrospectiva com pelo menos duas datas observadas, derivada das frentes.",
                "",
                f"- Eventos totais: **{quality['all_events']:,}**",
                f"- Eventos multidiários: **{quality['multiday_events']:,}**",
                f"- Fração multidiária: **{quality['multiday_fraction']:.2%}**",
                f"- Eventos de uma observação: **{quality['single_observation_events']:,}**",
                "",
                "A análise não inclui meteorologia e não altera a revisão observacional v1.0.0.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return quality
