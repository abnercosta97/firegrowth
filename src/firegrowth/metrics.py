"""Métricas puras para regressão de crescimento."""

from __future__ import annotations

import numpy as np


def regression_metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """Compute MAE, RMSE and signed mean bias on finite paired values."""
    obs = np.asarray(observed, dtype=float)
    pred = np.asarray(predicted, dtype=float)
    if obs.shape != pred.shape:
        raise ValueError("observed and predicted must have the same shape")
    mask = np.isfinite(obs) & np.isfinite(pred)
    if not np.any(mask):
        return {"mae": float("nan"), "rmse": float("nan"), "bias": float("nan"), "n": 0.0}
    error = pred[mask] - obs[mask]
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "bias": float(np.mean(error)),
        "n": float(mask.sum()),
    }
