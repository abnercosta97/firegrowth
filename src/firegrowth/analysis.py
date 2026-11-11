"""Análises estatísticas dos eventos, sem dependência meteorológica."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import read_table, validate_release
from .pipeline import _write_parquet, build_supervised
from .splits import temporal_split


def _read_parquet(path: Path) -> pd.DataFrame:
    import duckdb

    return (
        duckdb.connect(database=":memory:")
        .execute("SELECT * FROM read_parquet(?)", [str(path)])
        .fetchdf()
    )


def _summary(values: pd.Series) -> dict[str, float | int | None]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "n": int(numeric.size),
        "mean": float(numeric.mean()),
        "median": float(numeric.median()),
        "min": float(numeric.min()),
        "max": float(numeric.max()),
    }


def build_event_summary(
    events: pd.DataFrame,
    fronts: pd.DataFrame,
    sensors: pd.DataFrame,
    event_daily: pd.DataFrame,
) -> pd.DataFrame:
    """Build one descriptive row per event from published observations."""
    daily = event_daily.copy()
    daily["observation_date"] = pd.to_datetime(daily["observation_date"])
    daily = daily.sort_values(["event_id", "observation_date"])
    daily["gap_days"] = daily.groupby("event_id")["observation_date"].diff().dt.days
    daily["area_increment_ha"] = daily.groupby("event_id")["cumulative_area_ha"].diff()
    daily["growth_ha_day"] = daily["area_increment_ha"] / daily["gap_days"]
    daily_stats = (
        daily.groupby("event_id")
        .agg(
            observed_days=("observation_date", "nunique"),
            first_observation=("observation_date", "min"),
            last_observation=("observation_date", "max"),
            initial_area_ha=("cumulative_area_ha", "first"),
            final_area_ha=("cumulative_area_ha", "last"),
            max_growth_ha_day=("growth_ha_day", "max"),
            mean_growth_ha_day=("growth_ha_day", "mean"),
            median_growth_ha_day=("growth_ha_day", "median"),
            max_gap_days=("gap_days", "max"),
        )
        .reset_index()
    )
    daily_stats["calendar_duration_days"] = (
        daily_stats["last_observation"] - daily_stats["first_observation"]
    ).dt.days + 1
    daily_stats["total_growth_ha"] = daily_stats["final_area_ha"] - daily_stats["initial_area_ha"]
    front_stats = (
        fronts.groupby("event_id")
        .agg(
            front_count=("front_id", "nunique"),
            fronts_inside_matopiba=("matopiba_intersects", "sum"),
        )
        .reset_index()
    )
    sensor_stats = (
        sensors.groupby("front_id")["sensor_id"]
        .nunique()
        .rename("sensor_count")
        .reset_index()
        .merge(fronts[["front_id", "event_id"]].drop_duplicates(), on="front_id", how="left")
        .groupby("event_id")["sensor_count"]
        .sum()
        .rename("sensor_associations")
        .reset_index()
    )
    event_info = events[
        [
            "event_id",
            "status_code",
            "status_label",
            "type_code",
            "type_label",
            "date_min_utc",
            "date_max_utc",
        ]
    ].copy()
    result = event_info.merge(daily_stats, on="event_id", how="left")
    result = result.merge(front_stats, on="event_id", how="left")
    return result.merge(sensor_stats, on="event_id", how="left")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _figures(
    event_summary: pd.DataFrame, event_daily: pd.DataFrame, target: pd.DataFrame, out: Path
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out.mkdir(parents=True, exist_ok=True)
    dates = pd.to_datetime(event_summary["first_observation"])
    monthly = dates.dt.to_period("M").value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(10, 4))
    monthly.plot(ax=ax)
    ax.set(title="Eventos iniciados por mês", xlabel="Mês", ylabel="Eventos")
    fig.tight_layout()
    fig.savefig(out / "events_by_month.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(np.log1p(event_summary["front_count"].dropna()), bins=40)
    ax.set(title="Número de frentes por evento", xlabel="log(1 + frentes)", ylabel="Eventos")
    fig.tight_layout()
    fig.savefig(out / "fronts_per_event.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(event_summary["calendar_duration_days"].dropna(), bins=50)
    ax.set(title="Duração calendário dos eventos", xlabel="Dias", ylabel="Eventos")
    fig.tight_layout()
    fig.savefig(out / "event_duration.png", dpi=160)
    plt.close(fig)

    growth = event_daily["growth_ha_day"].replace([np.inf, -np.inf], np.nan).dropna()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(np.clip(growth, growth.quantile(0.01), growth.quantile(0.99)), bins=60)
    ax.set(
        title="Crescimento observado por dia",
        xlabel="ha/dia (limitado aos percentis 1–99)",
        ylabel="Evento–dia",
    )
    fig.tight_layout()
    fig.savefig(out / "growth_distribution.png", dpi=160)
    plt.close(fig)

    counts = target.groupby(["horizon_days", "eligible"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(6, 4))
    counts.plot(kind="bar", ax=ax)
    ax.set(title="Elegibilidade por horizonte", xlabel="Horizonte (dias)", ylabel="Referências")
    fig.tight_layout()
    fig.savefig(out / "target_eligibility.png", dpi=160)
    plt.close(fig)


def run_exploratory_analysis(
    dataset_root: str | Path, benchmark_root: str | Path, report_root: str | Path
) -> dict[str, object]:
    """Generate descriptive tables, figures and a Markdown report."""
    root, benchmark, report = Path(dataset_root), Path(benchmark_root), Path(report_root)
    report.mkdir(parents=True, exist_ok=True)
    validation = validate_release(root)
    if not validation["valid"]:
        raise ValueError(validation["errors"])
    events = read_table(root, "events")
    fronts = read_table(root, "fronts")
    sensors = read_table(root, "front_sensors")
    detections = read_table(root, "detections")
    coverage = read_table(root, "coverage")
    event_daily = _read_parquet(benchmark / "event_daily.parquet")
    summary = build_event_summary(events, fronts, sensors, event_daily)
    summary["start_year"] = pd.to_datetime(summary["first_observation"]).dt.year
    summary["start_month"] = pd.to_datetime(summary["first_observation"]).dt.month
    summary["crosses_year_boundary"] = (
        pd.to_datetime(summary["first_observation"]).dt.year
        != pd.to_datetime(summary["last_observation"]).dt.year
    )
    _write_parquet(summary, report / "event_summary.parquet")
    for column in ["status_label", "type_label", "start_year", "start_month"]:
        _write_csv(
            summary[column]
            .value_counts(dropna=False)
            .rename_axis(column)
            .reset_index(name="events"),
            report / f"{column}_counts.csv",
        )
    _write_csv(
        summary.describe(include="all").transpose().reset_index(), report / "event_statistics.csv"
    )
    _write_csv(
        fronts.assign(observation_date=pd.to_datetime(fronts["observation_date_utc"]).dt.date)
        .groupby("observation_date")
        .size()
        .rename("fronts")
        .reset_index(),
        report / "temporal_front_statistics.csv",
    )
    detection_datetime = "datetime_utc" if "datetime_utc" in detections else "data_hora"
    _write_csv(
        detections.assign(
            observation_date=pd.to_datetime(detections[detection_datetime], errors="coerce").dt.date
        )
        .groupby("observation_date")
        .size()
        .rename("detections")
        .reset_index(),
        report / "temporal_detection_statistics.csv",
    )
    _write_csv(
        detections.groupby(["estado", "municipio"], dropna=False)
        .size()
        .rename("detections")
        .reset_index()
        .sort_values("detections", ascending=False),
        report / "spatial_detection_statistics.csv",
    )
    targets = []
    for horizon in (1, 3):
        target = build_supervised(event_daily, coverage, horizon)
        target["partition"] = "unassigned"
        parts = temporal_split(target, target_end_column="target_end")
        for name, part in parts.items():
            if name != "excluded":
                target.loc[part.index, "partition"] = name
        targets.append(target)
    target = pd.concat(targets, ignore_index=True)
    _write_parquet(target, report / "target_statistics.parquet")
    _write_csv(
        target.groupby(["horizon_days", "partition", "eligible"])
        .agg(references=("event_id", "size"), events=("event_id", "nunique"))
        .reset_index(),
        report / "target_eligibility_statistics.csv",
    )
    _write_csv(
        coverage.groupby(
            ["processing_complete", "observation_available", "known_gap"], dropna=False
        )
        .size()
        .rename("days")
        .reset_index(),
        report / "coverage_statistics.csv",
    )
    _figures(
        summary,
        event_daily.assign(observation_date=pd.to_datetime(event_daily["observation_date"])).assign(
            gap_days=lambda x: x.groupby("event_id")["observation_date"].diff().dt.days,
            growth_ha_day=lambda x: (
                x.groupby("event_id")["cumulative_area_ha"].diff() / x["gap_days"]
            ),
        ),
        target,
        report / "figures",
    )
    quality = {
        "dataset_validation": validation,
        "events": int(len(events)),
        "fronts": int(len(fronts)),
        "detections": int(len(detections)),
        "event_days": int(len(event_daily)),
        "events_with_multiple_days": int((summary["observed_days"] > 1).sum()),
        "events_with_single_day": int((summary["observed_days"] == 1).sum()),
        "events_crossing_year_boundary": int(summary["crosses_year_boundary"].sum()),
        "meteorology_included": False,
    }
    (report / "quality_report.json").write_text(
        json.dumps(quality, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# Análise exploratória dos eventos",
        "",
        (
            "Análise descritiva sem meteorologia. O crescimento representa a extensão "
            "geométrica observada pelo catálogo, não área queimada física."
        ),
        "",
        f"- Eventos: **{quality['events']:,}**",
        f"- Frentes: **{quality['fronts']:,}**",
        f"- Detecções: **{quality['detections']:,}**",
        f"- Linhas evento–dia: **{quality['event_days']:,}**",
        f"- Eventos com uma única data observada: **{quality['events_with_single_day']:,}**",
        f"- Eventos com múltiplas datas observadas: **{quality['events_with_multiple_days']:,}**",
        f"- Eventos que atravessam anos: **{quality['events_crossing_year_boundary']:,}**",
        "",
        "## Interpretação",
        "",
        (
            "A ausência de uma frente não foi convertida automaticamente em crescimento zero. "
            "A tabela de detecções não foi agregada por evento porque o vínculo histórico "
            "foco–evento/frente não está disponível."
        ),
        "",
        "## Arquivos",
        "",
        (
            "As tabelas CSV, Parquet, relatório de qualidade e figuras nesta pasta documentam "
            "as estatísticas produzidas. A meteorologia não foi incluída."
        ),
    ]
    (report / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return quality
