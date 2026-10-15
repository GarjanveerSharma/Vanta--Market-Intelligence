"""Small, dependency-light indicator helpers (numpy only)."""
import numpy as np


def ema(values: np.ndarray, period: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    out = np.empty_like(values)
    if len(values) == 0:
        return out
    k = 2 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(closes: np.ndarray, period: int = 14) -> float:
    """Wilder's RSI of the last value. Returns 50 when there is not enough data."""
    closes = np.asarray(closes, dtype=float)
    if len(closes) <= period:
        return 50.0
    deltas = np.diff(closes)
    gains = np.clip(deltas, 0, None)
    losses = np.clip(-deltas, 0, None)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def atr_pct(highs, lows, closes, period: int = 14) -> np.ndarray:
    """Average true range as a fraction of price, per bar."""
    highs, lows, closes = (np.asarray(a, dtype=float) for a in (highs, lows, closes))
    prev_close = np.concatenate([[closes[0]], closes[:-1]])
    tr = np.maximum.reduce([highs - lows, np.abs(highs - prev_close), np.abs(lows - prev_close)])
    atr = ema(tr, period)
    return atr / np.where(closes == 0, 1, closes)


def zscore_last(values, window: int = 50) -> float:
    values = np.asarray(values, dtype=float)
    if len(values) < 3:
        return 0.0
    hist = values[-window - 1:-1]
    sd = hist.std()
    if sd == 0:
        return 0.0
    return float((values[-1] - hist.mean()) / sd)


def squash(x: float, scale: float) -> float:
    """Map any real number smoothly into (-1, 1)."""
    if scale == 0:
        return 0.0
    return float(np.tanh(x / scale))
