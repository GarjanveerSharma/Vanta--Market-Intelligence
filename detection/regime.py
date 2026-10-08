from __future__ import annotations

from collections.abc import Iterable, Mapping

import pandas as pd

from config.settings import get_settings


def detect_market_regime(
    candles: Iterable[Mapping[str, object]],
    adx_period: int = 14,
    atr_period: int = 14,
    adx_threshold: float | None = None,
    high_volatility_atr_pct: float | None = None,
) -> dict[str, float | str | bool | None]:
    rows = list(candles)
    if adx_period < 2 or atr_period < 2:
        raise ValueError("ADX and ATR periods must be at least 2")
    settings = get_settings()
    adx_floor = adx_threshold if adx_threshold is not None else settings.regime_adx_threshold
    high_vol_floor = (
        high_volatility_atr_pct
        if high_volatility_atr_pct is not None
        else settings.regime_high_volatility_atr_pct
    )
    if adx_floor <= 0 or high_vol_floor <= 0:
        raise ValueError("regime thresholds must be positive")
    if len(rows) < max(adx_period * 2, atr_period + 1):
        return {"regime": "SIDEWAYS", "adx": None, "atr": None, "atr_pct": None, "ready": False}

    frame = pd.DataFrame(rows)
    required = {"high", "low", "close"}
    if not required.issubset(frame.columns):
        raise ValueError("15-minute candles must include high, low, and close")
    frame = frame[["high", "low", "close"]].astype(float)
    if not all(frame[column].map(lambda value: pd.notna(value) and value > 0).all()
               for column in ("high", "low", "close")):
        raise ValueError("15-minute OHLC values must be finite and positive")

    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.ewm(alpha=1 / atr_period, adjust=False, min_periods=atr_period).mean()
    upward = frame["high"].diff()
    downward = -frame["low"].diff()
    plus_dm = upward.where((upward > downward) & (upward > 0), 0.0)
    minus_dm = downward.where((downward > upward) & (downward > 0), 0.0)
    plus_di = 100 * plus_dm.ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period).mean() / atr
    denominator = plus_di + minus_di
    dx = 100 * (plus_di - minus_di).abs() / denominator.where(denominator != 0)
    adx = dx.ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period).mean()

    current_adx = float(adx.fillna(0.0).iloc[-1])
    current_atr = float(atr.iloc[-1])
    current_close = float(frame["close"].iloc[-1])
    current_atr_pct = current_atr / current_close * 100
    if current_atr_pct >= high_vol_floor:
        regime = "HIGH_VOLATILITY"
    elif (
        current_adx >= adx_floor
        and float(plus_di.fillna(0.0).iloc[-1]) > float(minus_di.fillna(0.0).iloc[-1])
    ):
        regime = "TRENDING_UP"
    elif current_adx >= adx_floor:
        regime = "TRENDING_DOWN"
    else:
        regime = "SIDEWAYS"
    return {
        "regime": regime,
        "adx": current_adx,
        "atr": current_atr,
        "atr_pct": current_atr_pct,
        "ready": True,
    }
