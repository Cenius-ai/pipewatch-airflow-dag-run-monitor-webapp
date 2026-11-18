"""Small numeric helpers used by the seed and the query service."""

from __future__ import annotations

from typing import Sequence


def percentile(values: Sequence[float], quantile: float) -> float:
    """Linear-interpolation percentile (the same definition Airflow dashboards use)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * min(max(quantile, 0.0), 1.0)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(float(ordered[lower]) * (1 - weight) + float(ordered[upper]) * weight, 1)
