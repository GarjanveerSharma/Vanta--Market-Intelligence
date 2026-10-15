"""Market Mood Meter: a 0-100 Fear/Greed-style score built only from Vanta's own market data."""
import numpy as np

from .indicators import atr_pct, ema, rsi, squash

WEIGHTS = {"rsi": 0.25, "momentum": 0.25, "trend": 0.20, "volatility": 0.15, "volume": 0.15}
LABELS = [(20, "Extreme Fear"), (40, "Fear"), (60, "Neutral"), (80, "Greed"), (101, "Extreme Greed")]


def label_for(score: float) -> str:
    for limit, name in LABELS:
        if score < limit:
            return name
    return LABELS[-1][1]


def coin_mood(highs, lows, closes, volumes) -> dict:
    """Expects ~200 hourly candles. Each component is scaled to 0-100 (50 = neutral)."""
    closes = np.asarray(closes, dtype=float)
    volumes = np.asarray(volumes, dtype=float)
    if len(closes) < 60:
        return {"score": 50.0, "label": "Neutral", "components": {}, "insufficient_data": True}

    ret_24h = closes[-1] / closes[-25] - 1
    ema50 = ema(closes, 50)[-1]
    atrp = atr_pct(highs, lows, closes)
    vol_ratio = atrp[-24:].mean() / max(np.median(atrp[-168:]), 1e-12)
    vol_24 = volumes[-24:].sum()
    vol_prev = volumes[-168:-24].sum() / 6 if len(volumes) >= 168 else volumes[:-24].mean() * 24
    volume_ratio = vol_24 / max(vol_prev, 1e-12)

    comp = {
        "rsi": rsi(closes, 14),
        "momentum": 50 + 50 * squash(ret_24h, 0.05),
        "trend": 50 + 50 * squash(closes[-1] / ema50 - 1, 0.03),
        "volatility": 50 - 50 * squash(vol_ratio - 1, 0.5),            # rising volatility = fear
        "volume": 50 + 50 * squash(np.log(max(volume_ratio, 1e-6)), 0.7) * np.sign(ret_24h),  # volume confirms direction
    }
    comp = {k: float(np.clip(v, 0, 100)) for k, v in comp.items()}
    score = float(sum(comp[k] * w for k, w in WEIGHTS.items()))
    return {"score": round(score, 1), "label": label_for(score),
            "components": {k: round(v, 1) for k, v in comp.items()},
            "change_24h_pct": round(ret_24h * 100, 2)}


def market_mood(per_coin: dict[str, dict]) -> dict:
    valid = {s: m for s, m in per_coin.items() if not m.get("insufficient_data")}
    if not valid:
        return {"score": 50.0, "label": "Neutral", "coins": per_coin, "components": {}}
    score = float(np.mean([m["score"] for m in valid.values()]))
    components = {k: round(float(np.mean([m["components"][k] for m in valid.values()])), 1) for k in WEIGHTS}
    return {"score": round(score, 1), "label": label_for(score), "components": components, "weights": WEIGHTS,
            "coins": per_coin}
