from __future__ import annotations

from typing import Mapping

EVENTS = ("pump", "dump", "breakout", "whale", "volume_spike", "rsi_oversold", "rsi_overbought")


def evaluate_rules(features: Mapping[str, float]) -> list[dict[str, object]]:
    price = float(features["price"])
    change = float(features.get("change_1h", 0.0))
    return_1m = float(features.get("return_1m", 0.0))
    rsi = float(features.get("rsi", 50.0))
    volume_z = float(features.get("volume_z", 0.0))
    resistance = float(features.get("resistance", price))
    support = float(features.get("support", price))
    if price <= 0:
        raise ValueError("price must be positive")

    events: list[dict[str, object]] = []
    if change >= 5.0 and volume_z >= 2.0:
        events.append({"event_type": "pump", "confidence": min(0.95, 0.55 + change / 30 + volume_z / 20)})
    if change <= -5.0 and volume_z >= 2.0:
        events.append({"event_type": "dump", "confidence": min(0.95, 0.55 + abs(change) / 30 + volume_z / 20)})
    if price >= resistance and volume_z >= 1.0 and 35.0 <= rsi <= 75.0:
        events.append({"event_type": "breakout", "confidence": min(0.9, 0.55 + volume_z / 15)})
    if abs(return_1m) >= 0.01 and volume_z >= 3.0:
        events.append({"event_type": "whale", "confidence": min(0.85, 0.5 + abs(return_1m) * 8 + volume_z / 30)})
    if volume_z >= 3.0:
        events.append({"event_type": "volume_spike", "confidence": min(0.9, 0.55 + volume_z / 20)})
    if rsi <= 30.0:
        events.append({"event_type": "rsi_oversold", "confidence": min(0.85, 0.55 + (30.0 - rsi) / 100)})
    if rsi >= 70.0:
        events.append({"event_type": "rsi_overbought", "confidence": min(0.85, 0.55 + (rsi - 70.0) / 100)})
    if support > price:
        raise ValueError("support cannot be above the current price")
    return events