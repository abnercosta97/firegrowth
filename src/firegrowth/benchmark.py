"""Benchmark mínimo de baselines para regressão de crescimento."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import regression_metrics


def baseline_predictions(frame: pd.DataFrame, value_column: str, method: str) -> np.ndarray:
    """Generate deterministic predictions from prior observations."""
    if value_column not in frame:
        raise KeyError(value_column)
    if method == "zero":
        return np.zeros(len(frame), dtype=float)
    if method == "last_value":
        return np.asarray(frame["last_growth_ha_day"], dtype=float)
    if method == "moving_average":
        return np.asarray(frame["moving_average_growth_ha_day"], dtype=float)
    raise ValueError(f"unknown baseline: {method}")


def score_predictions(observed: np.ndarray, predicted: np.ndarray, model: str) -> dict[str, object]:
    """Return metrics with the model name attached."""
    return {"model": model, **regression_metrics(observed, predicted)}
