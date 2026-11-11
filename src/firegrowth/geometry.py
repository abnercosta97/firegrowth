"""Operações geométricas para a extensão observada dos eventos."""

from __future__ import annotations

from collections.abc import Iterable

from pyproj import Transformer
from shapely import from_wkt
from shapely.ops import transform, unary_union

_TO_EQUAL_AREA = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True).transform


def union_area_hectares(wkts: Iterable[str | None]) -> float:
    """Return the equal-area union of WKT geometries in hectares."""
    geometries = [from_wkt(value) for value in wkts if value]
    if not geometries:
        return float("nan")
    projected = transform(_TO_EQUAL_AREA, unary_union(geometries))
    return float(projected.area / 10_000.0)
