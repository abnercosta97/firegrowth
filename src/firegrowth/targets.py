"""Construção do alvo a partir de datas e áreas cumulativas observadas."""

from __future__ import annotations

import numpy as np
import pandas as pd


def cumulative_area_growth(areas_ha: np.ndarray, horizon_days: int = 1) -> np.ndarray:
    """Return growth over a fixed number of consecutive observations."""
    values = np.asarray(areas_ha, dtype=float)
    if values.ndim != 1:
        raise ValueError("areas_ha must be one-dimensional")
    if horizon_days < 1:
        raise ValueError("horizon_days must be positive")
    result = np.full(values.shape, np.nan, dtype=float)
    if horizon_days < len(values):
        result[:-horizon_days] = (values[horizon_days:] - values[:-horizon_days]) / horizon_days
    return result


def dated_growth(
    frame: pd.DataFrame,
    date_column: str = "observation_date",
    area_column: str = "cumulative_area_ha",
    horizon_days: int = 1,
) -> pd.Series:
    """Calculate growth only when the exact future calendar date exists.

    Missing calendar days are not silently treated as zero growth.
    """
    if horizon_days < 1:
        raise ValueError("horizon_days must be positive")
    dates = pd.to_datetime(frame[date_column]).dt.normalize()
    areas = pd.Series(frame[area_column].to_numpy(float), index=dates)
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    for index, reference in zip(frame.index, dates, strict=True):
        future = areas.get(reference + pd.Timedelta(days=horizon_days))
        current = areas.get(reference)
        if future is not None and current is not None and pd.notna(future) and pd.notna(current):
            result.loc[index] = (future - current) / horizon_days
    return result
