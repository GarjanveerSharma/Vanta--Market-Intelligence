from detection.regime import detect_market_regime


def test_regime_detector_classifies_direction_and_volatility():
    rising = [
        {"high": 100 + index * 0.5 + 0.2, "low": 100 + index * 0.5 - 0.2, "close": 100 + index * 0.5}
        for index in range(60)
    ]
    falling = [
        {"high": 130 - index * 0.5 + 0.2, "low": 130 - index * 0.5 - 0.2, "close": 130 - index * 0.5}
        for index in range(60)
    ]
    sideways = [{"high": 100.2, "low": 99.8, "close": 100.0} for _ in range(60)]

    assert detect_market_regime(rising)["regime"] == "TRENDING_UP"
    assert detect_market_regime(falling)["regime"] == "TRENDING_DOWN"
    assert detect_market_regime(sideways)["regime"] == "SIDEWAYS"
    assert detect_market_regime(rising[:20])["ready"] is False
