from __future__ import annotations

from collections.abc import Mapping, Sequence


def calculate_metrics(
    event_counts: Mapping[str, Mapping[str, float]],
    equity: Sequence[Mapping[str, object]],
    true_positives: int,
    false_negatives: int,
    avg_latency_ms: float,
) -> dict[str, object]:
    total_alerts = sum(int(values["alerts"]) for values in event_counts.values())
    precision = true_positives / total_alerts if total_alerts else 0.0
    recall_denominator = true_positives + false_negatives
    recall = true_positives / recall_denominator if recall_denominator else 0.0
    ending_equity = float(equity[-1]["equity"]) if equity else 10_000.0
    by_event = [
        {
            "event_type": event_type,
            "alerts": int(values["alerts"]),
            "true_positives": int(values["true_positives"]),
            "precision": (
                float(values["true_positives"]) / int(values["alerts"])
                if int(values["alerts"]) else 0.0
            ),
            "avg_lead_seconds": (
                float(values["lead_seconds"]) / int(values["lead_count"])
                if int(values["lead_count"]) else 0.0
            ),
        }
        for event_type, values in sorted(event_counts.items())
    ]
    return {
        "total_alerts": total_alerts,
        "precision": precision,
        "recall": recall,
        "avg_latency_ms": avg_latency_ms,
        "pnl_pct": (ending_equity / 10_000.0 - 1.0) * 100.0,
        "by_event": by_event,
        "equity": list(equity),
    }