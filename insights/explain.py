"""'Why this signal?': which market conditions leaned bullish or bearish at a given moment.

Scores run from -1 (strongly bearish) to +1 (strongly bullish). Volatility is a risk
factor: it only ever lowers confidence, it doesn't pick a direction.
"""
import numpy as np

from .indicators import atr_pct, ema, rsi, squash, zscore_last


def _effect(score: float, risk: bool = False) -> str:
    if risk:
        return "risk" if score < -0.2 else "neutral"
    if score > 0.15:
        return "bullish"
    if score < -0.15:
        return "bearish"
    return "neutral"


def explain(opens, highs, lows, closes, volumes) -> dict:
    closes = np.asarray(closes, dtype=float)
    if len(closes) < 60:
        return {"factors": [], "net_score": 0.0, "leaning": "neutral", "insufficient_data": True}
    volumes = np.asarray(volumes, dtype=float)

    r = rsi(closes, 14)
    mom = closes[-1] / closes[-13] - 1
    e20, e50 = ema(closes, 20)[-1], ema(closes, 50)[-1]
    trend = e20 / e50 - 1
    vz = zscore_last(volumes, 50)
    last_move = closes[-1] / float(np.asarray(opens, dtype=float)[-1]) - 1
    atrp = atr_pct(highs, lows, closes)
    vol_ratio = atrp[-1] / max(np.median(atrp[-100:]), 1e-12)

    factors = [
        {"key": "rsi", "name": "RSI (14)", "value": f"{r:.1f}",
         "score": float(np.clip((50 - r) / 30, -1, 1)),
         "detail": "Oversold (<30) leans bullish, overbought (>70) leans bearish."},
        {"key": "momentum", "name": "Momentum (12 bars)", "value": f"{mom * 100:+.2f}%",
         "score": squash(mom, 0.01), "detail": "Recent price direction."},
        {"key": "trend", "name": "Trend (EMA 20 vs 50)", "value": f"{trend * 100:+.2f}%",
         "score": squash(trend, 0.004), "detail": "Short-term average above the longer one is bullish."},
        {"key": "volume", "name": "Volume z-score", "value": f"{vz:+.2f}",
         "score": squash(vz, 3) * float(np.sign(last_move)) if vz > 0 else 0.0,
         "detail": "Unusual volume confirms the direction of the latest candle."},
        {"key": "volatility", "name": "Volatility", "value": f"{vol_ratio:.2f}× normal",
         "score": -max(0.0, squash(vol_ratio - 1, 1.0)), "risk": True,
         "detail": "Higher than normal volatility lowers confidence."},
    ]
    for f in factors:
        f["score"] = round(float(f["score"]), 3)
        f["effect"] = _effect(f["score"], f.get("risk", False))

    directional = [f["score"] for f in factors if not f.get("risk")]
    net = float(np.mean(directional))
    risk_penalty = -factors[-1]["score"]
    return {
        "factors": factors,
        "net_score": round(net, 3),
        "leaning": _effect(net),
        "risk_penalty": round(risk_penalty, 3),
        "note": "Market conditions at that moment. They explain the context of a signal, not the exact rule that fired.",
    }
