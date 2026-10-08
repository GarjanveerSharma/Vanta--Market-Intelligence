from __future__ import annotations

from typing import Mapping

from detection.rules import evaluate_rules
from detection.timeframes import confirm_timeframes


def classify(
    features: Mapping[str, float],
    regime: str = "SIDEWAYS",
) -> dict[str, float | str | list[dict[str, object]]]:
    events = evaluate_rules(features)
    if regime == "TRENDING_UP":
        events = [event for event in events if event["event_type"] != "rsi_overbought"]
    elif regime == "TRENDING_DOWN":
        events = [event for event in events if event["event_type"] != "rsi_oversold"]
    if not events:
        return {"signal": "HOLD", "confidence": 0.0, "events": []}
    priority = {
        "dump": 7, "pump": 6, "breakout": 5, "rsi_oversold": 4,
        "rsi_overbought": 4, "whale": 2, "volume_spike": 1,
    }
    primary = max(events, key=lambda event: (priority[str(event["event_type"])], float(event["confidence"])))
    signal_by_event = {
        "pump": "SELL",
        "dump": "AVOID",
        "breakout": "BUY",
        "whale": "HOLD",
        "volume_spike": "HOLD",
        "rsi_oversold": "BUY",
        "rsi_overbought": "SELL",
    }
    return {
        "signal": signal_by_event[str(primary["event_type"])],
        "confidence": float(primary["confidence"]),
        "events": events,
    }