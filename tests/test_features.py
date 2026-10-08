import math

import pytest

from processing.features import calculate_features, rsi


def test_rsi_handles_rising_falling_and_flat_prices():
    assert rsi([1, 2, 3, 4]) == 100.0
    assert rsi([4, 3, 2, 1]) == 0.0
    assert rsi([4, 4, 4, 4]) == 50.0


def test_feature_output_is_finite_and_has_expected_fields():
    candles = [
        {"time": index, "close": 100 + index, "volume": 10 + index}
        for index in range(25)
    ]
    result = calculate_features(candles)
    assert result["price"] == 124.0
    assert result["rsi"] == 100.0
    assert result["candle_count"] == 25.0
    assert all(math.isfinite(value) for value in result.values())


@pytest.mark.parametrize("candles", [[], [{"close": float("nan"), "volume": 1}]])
def test_feature_calculation_rejects_empty_or_non_finite_data(candles):
    with pytest.raises(ValueError):
        calculate_features(candles)


def test_feature_calculation_requires_positive_close():
    with pytest.raises(ValueError, match="positive"):
        calculate_features([{"close": 0, "volume": 1}])