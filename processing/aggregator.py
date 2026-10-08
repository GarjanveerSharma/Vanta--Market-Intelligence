from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from processing.features import calculate_features


def aggregate_candles(candles: Sequence[Mapping[str, object]]) -> dict[str, float]:
    if not candles:
        raise ValueError("Cannot aggregate an empty candle sequence")
    ordered = sorted(candles, key=lambda candle: pd.Timestamp(candle["time"]).value)
    return calculate_features(ordered)


def resample_candles(
    candles: Sequence[Mapping[str, object]],
    minutes: int,
) -> list[dict[str, object]]:
    if minutes < 1:
        raise ValueError("resample interval must be positive")
    if not candles:
        return []
    frame = pd.DataFrame(candles)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").set_index("time")
    bars = frame.resample(f"{minutes}min", origin="start_day", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["open", "high", "low", "close"])
    bars.index.name = "time"
    return bars.reset_index().to_dict(orient="records")


def merge_candle_history(
    seeded: Sequence[Mapping[str, object]],
    live: Sequence[Mapping[str, object]],
    limit: int = 120,
) -> list[dict[str, object]]:
    if limit < 1:
        raise ValueError("history limit must be positive")
    merged = {pd.Timestamp(candle["time"]).value: dict(candle) for candle in seeded}
    merged.update({pd.Timestamp(candle["time"]).value: dict(candle) for candle in live})
    return sorted(merged.values(), key=lambda candle: pd.Timestamp(candle["time"]).value)[-limit:]