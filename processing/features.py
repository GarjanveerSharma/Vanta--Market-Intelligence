from __future__ import annotations

from math import isfinite, sqrt
from statistics import mean, pstdev
from typing import Iterable, Mapping


def _finite(values: Iterable[float]) -> list[float]:
    result = [float(value) for value in values]
    if not result or not all(isfinite(value) for value in result):
        raise ValueError("Candle values must be a non-empty sequence of finite numbers")
    return result


def rsi(closes: Iterable[float], period: int = 14) -> float:
    values = _finite(closes)
    if period < 1:
        raise ValueError("period must be positive")
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    recent = deltas[-period:]
    if not recent:
        return 50.0
    gains = sum(max(delta, 0.0) for delta in recent) / len(recent)
    losses = sum(max(-delta, 0.0) for delta in recent) / len(recent)
    if losses == 0:
        return 100.0 if gains else 50.0
    return 100.0 - 100.0 / (1.0 + gains / losses)


def calculate_features(candles: Iterable[Mapping[str, object]]) -> dict[str, float]:
    rows = list(candles)
    if not rows:
        raise ValueError("At least one candle is required")
    closes = _finite(float(row["close"]) for row in rows)
    volumes = _finite(float(row["volume"]) for row in rows)
    current = closes[-1]
    if current <= 0:
        raise ValueError("Closing prices must be positive")
    previous = closes[-2] if len(closes) > 1 else current
    returns = [(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes))]
    recent_volumes = volumes[-20:]
    volume_mean = mean(recent_volumes)
    volume_std = pstdev(recent_volumes)
    volume_z = (volumes[-1] - volume_mean) / volume_std if volume_std else 0.0
    lookback = closes[-min(20, len(closes)):]
    return {
        "price": current,
        "change_1h": ((current / closes[max(0, len(closes) - 61)] - 1.0) * 100.0),
        "return_1m": (current / previous - 1.0) if previous else 0.0,
        "volatility": pstdev(returns[-20:]) if len(returns) > 1 else 0.0,
        "rsi": rsi(closes),
        "volume_z": volume_z,
        "resistance": max(lookback),
        "support": min(lookback),
        "volume_mean": volume_mean,
        "candle_count": float(len(rows)),
        "price_std": sqrt(mean([(value - mean(lookback)) ** 2 for value in lookback])),
    }