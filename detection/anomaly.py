from __future__ import annotations

from math import isfinite
from statistics import mean, pstdev
from typing import Iterable


def z_score(value: float, history: Iterable[float]) -> float:
    values = [float(item) for item in history]
    if not isfinite(value) or any(not isfinite(item) for item in values):
        raise ValueError("Anomaly inputs must be finite numbers")
    if len(values) < 2:
        return 0.0
    deviation = pstdev(values)
    return (value - mean(values)) / deviation if deviation else 0.0


def score_anomaly(
    current_return: float,
    return_history: Iterable[float],
    current_volume: float,
    volume_history: Iterable[float],
) -> dict[str, float | bool]:
    returns = list(return_history)
    volumes = list(volume_history)
    return_z = z_score(current_return, returns)
    volume_z = z_score(current_volume, volumes)
    combined = max(abs(return_z), abs(volume_z))
    return {
        "return_z": return_z,
        "volume_z": volume_z,
        "score": combined,
        "is_anomaly": combined >= 3.0,
    }