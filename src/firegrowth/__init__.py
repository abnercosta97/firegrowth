"""Contratos e funções centrais do benchmark de crescimento de fogo."""

from .metrics import regression_metrics
from .targets import cumulative_area_growth

__all__ = ["cumulative_area_growth", "regression_metrics"]
__version__ = "0.1.0"
