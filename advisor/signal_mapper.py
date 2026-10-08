from __future__ import annotations

from typing import Mapping

from advisor.guardrails import clamp_confidence
from advisor.templates import explain_event

EVENT_ACTIONS = {
    "pump": "SELL",
    "dump": "AVOID",
    "breakout": "BUY",
    "whale": "HOLD",
    "volume_spike": "HOLD",
    "rsi_oversold": "BUY",
    "rsi_overbought": "SELL",
}


def map_event(
    event: Mapping[str, object],
    price: float,
    risk_level: str = "medium",
    high_volatility: bool = False,
    stop_multiplier: float = 1.5,
    confidence_multiplier: float = 0.75,
    regime: str = "SIDEWAYS",
) -> dict[str, object]:
    event_type = str(event["event_type"])
    if event_type not in EVENT_ACTIONS:
        raise ValueError(f"Unsupported event type: {event_type}")
    if price <= 0:
        raise ValueError("price must be positive")
    if risk_level not in {"low", "medium", "high"}:
        raise ValueError("risk_level must be low, medium, or high")
    if stop_multiplier < 1 or not 0 < confidence_multiplier <= 1:
        raise ValueError("invalid high-volatility adjustment")
    action = EVENT_ACTIONS[event_type]
    confidence = clamp_confidence(float(event.get("confidence", 0.0)))
    distance = {"low": 0.02, "medium": 0.03, "high": 0.05}[risk_level]
    if high_volatility:
        distance *= stop_multiplier
        confidence *= confidence_multiplier
        confidence = clamp_confidence(confidence)
    stop_loss = price * (1 - distance) if action == "BUY" else price * (1 + distance)
    return {
        "action": action,
        "confidence": confidence,
        "stop_loss": round(stop_loss, 8),
        "explanation": explain_event(event_type, regime),
        "event_type": event_type,
    }