import pytest

from advisor.guardrails import clamp_confidence, safe_explanation
from advisor.signal_mapper import map_event
from backtest.download_data import interval_milliseconds
from backtest.replay import replay_candles


def test_event_mapping_sets_action_and_risk_adjusted_stop_level():
    mapped = map_event({"event_type": "breakout", "confidence": 0.8}, 100.0, "low")
    assert mapped["action"] == "BUY"
    assert mapped["stop_loss"] == 98.0
    assert mapped["confidence"] == 0.8


def test_high_volatility_lowers_confidence_and_widens_stop():
    normal = map_event({"event_type": "breakout", "confidence": 0.8}, 100.0)
    volatile = map_event(
        {"event_type": "breakout", "confidence": 0.8},
        100.0,
        high_volatility=True,
        stop_multiplier=1.5,
        confidence_multiplier=0.75,
    )
    assert volatile["confidence"] == pytest.approx(normal["confidence"] * 0.75)
    assert 100.0 - float(volatile["stop_loss"]) > 100.0 - float(normal["stop_loss"])


def test_explanation_guardrail_uses_fallback_for_empty_or_unsafe_text():
    assert safe_explanation("   ", "Deterministic fallback") == "Deterministic fallback"
    assert safe_explanation("Guaranteed profit tomorrow", "Fallback") == "Fallback"
    assert safe_explanation("  Market volume increased. ", "Fallback") == "Market volume increased."


def test_mapper_rejects_unknown_events_and_invalid_confidence():
    with pytest.raises(ValueError, match="Unsupported"):
        map_event({"event_type": "unknown"}, 100.0)
    with pytest.raises(ValueError, match="between 0 and 1"):
        clamp_confidence(1.2)


def test_binance_interval_parser_supports_multiple_units():
    assert interval_milliseconds("5m") == 300_000
    assert interval_milliseconds("2h") == 7_200_000
    with pytest.raises(ValueError):
        interval_milliseconds("invalid")


def test_backtest_replay_returns_dashboard_contract():
    candles = [
        {
            "time": f"2026-01-01T00:{index:02d}:00+00:00",
            "open": 100 + index * 0.1,
            "high": 101 + index * 0.1,
            "low": 99 + index * 0.1,
            "close": 100 + index * 0.1,
            "volume": 100.0,
        }
        for index in range(25)
    ]
    result = replay_candles(candles)
    assert {"total_alerts", "precision", "recall", "avg_latency_ms", "pnl_pct", "by_event", "equity"} <= result.keys()
    assert result["equity"]