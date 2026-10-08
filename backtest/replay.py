from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from time import perf_counter

from advisor.signal_mapper import EVENT_ACTIONS
from backtest.metrics import calculate_metrics
from detection.rules import evaluate_rules
from processing.aggregator import aggregate_candles

INITIAL_CAPITAL = 10_000.0
FORWARD_BARS = 3
SIGNIFICANT_MOVE = 0.003


def replay_candles(candles: Sequence[Mapping[str, object]]) -> dict[str, object]:
    ordered = sorted(candles, key=lambda candle: candle["time"])
    if len(ordered) < 20:
        raise ValueError("At least 20 candles are required for replay")
    event_counts: dict[str, dict[str, float]] = defaultdict(
        lambda: {"alerts": 0, "true_positives": 0, "lead_seconds": 0.0, "lead_count": 0}
    )
    equity = INITIAL_CAPITAL
    curve: list[dict[str, object]] = []
    true_positives = 0
    false_negatives = 0
    replay_started = perf_counter()

    for index in range(19, len(ordered) - FORWARD_BARS):
        window = ordered[max(0, index - 119):index + 1]
        features = aggregate_candles(window)
        future_price = float(ordered[index + FORWARD_BARS]["close"])
        current_price = float(ordered[index]["close"])
        forward_return = future_price / current_price - 1.0
        directional_move = abs(forward_return) >= SIGNIFICANT_MOVE
        events = evaluate_rules(features)
        if directional_move and not events:
            false_negatives += 1
        for event in events:
            event_type = str(event["event_type"])
            counts = event_counts[event_type]
            counts["alerts"] += 1
            action = EVENT_ACTIONS[event_type]
            expected_direction = 1 if action == "BUY" else (-1 if action == "SELL" else 0)
            correct = directional_move and expected_direction != 0 and forward_return * expected_direction > 0
            if correct:
                counts["true_positives"] += 1
                true_positives += 1
            if directional_move and expected_direction != 0:
                timestamp = ordered[index + FORWARD_BARS]["time"]
                then = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(str(timestamp))
                start = ordered[index]["time"]
                start_time = start if isinstance(start, datetime) else datetime.fromisoformat(str(start))
                counts["lead_seconds"] += max(0.0, (then - start_time).total_seconds())
                counts["lead_count"] += 1
            if action in {"BUY", "SELL"}:
                equity *= max(0.0, 1.0 + 0.1 * forward_return * expected_direction)
            curve.append({
                "time": str(ordered[index + FORWARD_BARS]["time"]),
                "equity": equity,
            })

    if not curve:
        curve.append({"time": str(ordered[-1]["time"]), "equity": INITIAL_CAPITAL})
    average_latency = (perf_counter() - replay_started) * 1000 / len(ordered)
    return calculate_metrics(event_counts, curve, true_positives, false_negatives, average_latency)