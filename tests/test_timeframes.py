import pytest

from detection.timeframes import confirm_timeframes


def test_timeframe_confirmation_requires_two_of_three():
    buy = {"signal": "BUY", "confidence": 0.8, "events": []}
    sell = {"signal": "SELL", "confidence": 0.6, "events": []}

    result = confirm_timeframes({"1m": buy, "5m": buy, "15m": sell})

    assert result["signal"] == "BUY"
    assert result["quality"] == "partial"
    assert result["agreement"] == {"1m": True, "5m": True, "15m": False}
    assert result["confidence"] == pytest.approx(0.6)


def test_timeframe_confirmation_holds_without_a_majority():
    result = confirm_timeframes({
        "1m": {"signal": "BUY", "confidence": 0.8, "events": []},
        "5m": {"signal": "SELL", "confidence": 0.7, "events": []},
        "15m": {"signal": "HOLD", "confidence": 0.0, "events": []},
    })

    assert result["signal"] == "HOLD"
    assert result["quality"] == "unconfirmed"
    assert result["agreement"] == {"1m": False, "5m": False, "15m": False}
