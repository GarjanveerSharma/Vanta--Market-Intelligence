import pytest

from detection.anomaly import score_anomaly, z_score
from detection.classifier import classify, confirm_timeframes
from detection.regime import detect_market_regime
from detection.rules import evaluate_rules


def test_rules_detect_breakout_and_volume_spike():
    events = evaluate_rules({
        "price": 110.0,
        "change_1h": 1.0,
        "return_1m": 0.002,
        "rsi": 60.0,
        "volume_z": 3.5,
        "resistance": 109.0,
        "support": 100.0,
    })
    assert {event["event_type"] for event in events} == {"breakout", "volume_spike"}


def test_rules_detect_pump_and_dump():
    base = {"price": 100.0, "rsi": 50.0, "volume_z": 3.0, "support": 90.0, "resistance": 110.0}
    pump = evaluate_rules({**base, "change_1h": 8.0, "return_1m": 0.0})
    dump = evaluate_rules({**base, "change_1h": -8.0, "return_1m": 0.0})
    assert "pump" in {event["event_type"] for event in pump}
    assert "dump" in {event["event_type"] for event in dump}


def test_anomaly_score_is_stable_for_constant_history():
    assert z_score(10.0, [10.0, 10.0, 10.0]) == 0.0
    result = score_anomaly(0.1, [0.0, 0.01, -0.01], 500.0, [10.0, 11.0, 9.0])
    assert result["is_anomaly"] is True
    assert result["score"] > 3.0


def test_invalid_prices_are_rejected():
    with pytest.raises(ValueError, match="positive"):
        evaluate_rules({"price": 0})


def test_rsi_countertrend_signal_is_suppressed():
    oversold = {
        "price": 100.0,
        "rsi": 20.0,
        "volume_z": 0.0,
        "resistance": 101.0,
        "support": 99.0,
    }
    overbought = {**oversold, "rsi": 80.0}
    assert classify(oversold, "TRENDING_DOWN")["signal"] == "HOLD"
    assert classify(overbought, "TRENDING_UP")["signal"] == "HOLD"
    assert classify(oversold, "TRENDING_UP")["signal"] == "BUY"
    assert classify(overbought, "TRENDING_DOWN")["signal"] == "SELL"


def test_three_timeframe_confirmation_and_partial_confidence():
    buy = {"signal": "BUY", "confidence": 0.8, "events": []}
    sell = {"signal": "SELL", "confidence": 0.6, "events": []}
    confirmed = confirm_timeframes({"1m": buy, "5m": buy, "15m": buy})
    assert confirmed["signal"] == "BUY"
    assert confirmed["quality"] == "confirmed"
    assert all(confirmed["agreement"].values())
    partial = confirm_timeframes({"1m": buy, "5m": buy, "15m": sell})
    assert partial["signal"] == "BUY"
    assert partial["quality"] == "partial"
    assert partial["confidence"] == pytest.approx(0.6)
    assert partial["agreement"] == {"1m": True, "5m": True, "15m": False}
    rejected = confirm_timeframes({
        "1m": buy,
        "5m": sell,
        "15m": {"signal": "HOLD", "confidence": 0.0, "events": []},
    })
    assert rejected["signal"] == "HOLD"
    assert rejected["quality"] == "unconfirmed"
    assert rejected["events"] == []


def test_adx_atr_regime_detects_trend_sideways_and_high_volatility():
    rising = [
        {"high": 100 + i * 0.5 + 0.2, "low": 100 + i * 0.5 - 0.2, "close": 100 + i * 0.5}
        for i in range(60)
    ]
    falling = [
        {"high": 130 - i * 0.5 + 0.2, "low": 130 - i * 0.5 - 0.2, "close": 130 - i * 0.5}
        for i in range(60)
    ]
    sideways = [
        {"high": 100.2, "low": 99.8, "close": 100.0}
        for _ in range(60)
    ]
    volatile = [
        {
            "high": 100 + (i % 2) * 2.0 + 1.5,
            "low": 100 + (i % 2) * 2.0 - 1.5,
            "close": 100 + (i % 2) * 2.0,
        }
        for i in range(60)
    ]
    assert detect_market_regime(rising)["regime"] == "TRENDING_UP"
    assert detect_market_regime(falling)["regime"] == "TRENDING_DOWN"
    assert detect_market_regime(sideways)["regime"] == "SIDEWAYS"
    assert detect_market_regime(volatile, high_volatility_atr_pct=1.0)["regime"] == "HIGH_VOLATILITY"
    assert detect_market_regime(rising[:20])["ready"] is False