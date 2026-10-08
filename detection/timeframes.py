from __future__ import annotations

from collections.abc import Mapping

from advisor.signal_mapper import EVENT_ACTIONS

TIMEFRAMES = ("1m", "5m", "15m")
SIGNAL_DIRECTIONS = {"BUY": 1, "SELL": -1, "AVOID": -1}


def confirm_timeframes(
    timeframe_results: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    votes = {
        frame: SIGNAL_DIRECTIONS.get(str(timeframe_results.get(frame, {}).get("signal")), 0)
        for frame in TIMEFRAMES
    }
    buy_votes = sum(direction == 1 for direction in votes.values())
    sell_votes = sum(direction == -1 for direction in votes.values())
    winning_direction = 1 if buy_votes >= 2 else (-1 if sell_votes >= 2 else 0)
    supporting = [
        timeframe_results[frame]
        for frame in TIMEFRAMES
        if winning_direction and votes[frame] == winning_direction
    ]
    if winning_direction:
        confidence = sum(float(result["confidence"]) for result in supporting) / len(supporting)
        quality = "confirmed" if len(supporting) == 3 else "partial"
        if quality == "partial":
            confidence *= 0.75
        signal = "BUY" if winning_direction == 1 else "SELL"
    else:
        confidence = 0.0
        quality = "unconfirmed"
        signal = "HOLD"

    agreement = {
        frame: bool(winning_direction and votes[frame] == winning_direction)
        for frame in TIMEFRAMES
    }
    events: dict[str, dict[str, object]] = {}
    for result in supporting:
        for event in result.get("events", []):
            event_type = str(event["event_type"])
            action = EVENT_ACTIONS.get(event_type, "HOLD")
            if SIGNAL_DIRECTIONS.get(action, 0) != winning_direction:
                continue
            existing = events.get(event_type)
            if existing is None or float(event["confidence"]) > float(existing["confidence"]):
                events[event_type] = dict(event)
    return {
        "signal": signal,
        "confidence": confidence,
        "quality": quality,
        "agreement": agreement,
        "events": list(events.values()),
    }
