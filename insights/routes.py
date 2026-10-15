"""FastAPI routes: /insights/mood, /insights/explain, /insights/quant."""
import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException, Query

from . import data_source as ds
from .explain import explain
from .mood import coin_mood, market_mood
from .quant import buy_and_hold, random_baseline, simulate_trades, trade_metrics, verdict

log = logging.getLogger("vanta.insights")
router = APIRouter(prefix="/insights", tags=["insights"])

FEE = 0.001        # 0.1% per side (Binance spot default)
SLIPPAGE = 0.0005  # 0.05% per side


def _check_symbol(symbol: str) -> str:
    symbol = symbol.upper()
    if symbol not in ds.SYMBOLS:
        raise HTTPException(400, f"Unknown symbol. Use one of: {', '.join(ds.SYMBOLS)}")
    return symbol


def _parse_time_ms(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value if value > 1e11 else value * 1000)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


@router.get("/mood")
async def mood():
    if (hit := ds.cached(("mood",), 60)) is not None:
        return hit
    try:
        klines = await asyncio.gather(*(ds.fetch_klines(s, "1h", 200) for s in ds.SYMBOLS))
    except httpx.HTTPError as e:
        log.warning("mood: market data unavailable: %s", e)
        raise HTTPException(503, "Market data is temporarily unavailable.")
    per_coin = {s: coin_mood(k["high"], k["low"], k["close"], k["volume"]) for s, k in zip(ds.SYMBOLS, klines)}
    result = market_mood(per_coin)
    result["updated_at"] = int(time.time() * 1000)
    return ds.store(("mood",), result)


@router.get("/fx")
async def usd_inr():
    """Current USD/INR reference rate from the public ExchangeRate-API endpoint."""
    if (hit := ds.cached(("fx", "USD", "INR"), 3600)) is not None:
        return hit
    try:
        async with httpx.AsyncClient(timeout=ds.TIMEOUT) as client:
            response = await client.get("https://open.er-api.com/v6/latest/USD")
            response.raise_for_status()
        payload = response.json()
        rate = float(payload["rates"]["INR"])
        if payload.get("result") != "success" or rate <= 0:
            raise ValueError("Currency provider returned an invalid USD/INR rate.")
    except httpx.HTTPError as e:
        log.warning("fx: exchange rate unavailable: %s", e)
        raise HTTPException(503, "The USD/INR exchange rate is temporarily unavailable.")
    except (KeyError, TypeError, ValueError) as e:
        log.warning("fx: invalid exchange rate response: %s", e)
        raise HTTPException(502, "The exchange rate provider returned invalid data.")
    return ds.store(("fx", "USD", "INR"), {
        "base": "USD",
        "quote": "INR",
        "rate": rate,
        "updated_at": payload.get("time_last_update_unix"),
    })


@router.get("/explain")
async def explain_signal(symbol: str, interval: str = Query("5m", pattern="^(1m|5m|15m|1h)$"),
                         at: str | None = None):
    """Factor breakdown for a coin now, or at the time of a past signal (`at` = ISO time or epoch ms)."""
    symbol = _check_symbol(symbol)
    end_ms = _parse_time_ms(at)
    try:
        k = await ds.fetch_klines(symbol, interval, 200, end_ms)
    except httpx.HTTPError as e:
        log.warning("explain: market data unavailable: %s", e)
        raise HTTPException(503, "Market data is temporarily unavailable.")
    result = explain(k["open"], k["high"], k["low"], k["close"], k["volume"])
    result.update(symbol=symbol, interval=interval, at=end_ms)
    return result


@router.get("/quant")
async def quant(days: int = Query(7, ge=1, le=30), horizon_minutes: int = Query(60, ge=5, le=1440),
                allow_short: bool = True, symbol: str | None = None):
    symbols = [_check_symbol(symbol)] if symbol else ds.SYMBOLS
    key = ("quant", days, horizon_minutes, allow_short, tuple(symbols))
    if (hit := ds.cached(key, 300)) is not None:
        return hit

    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 86_400_000
    horizon_bars = max(1, horizon_minutes // 5)

    try:
        alerts = await ds.fetch_alerts(symbol=symbols[0] if symbol else None, limit=500)
        klines = await asyncio.gather(*(ds.fetch_klines_range(s, "5m", start_ms, end_ms) for s in symbols))
    except httpx.HTTPError as e:
        log.warning("quant: data unavailable: %s", e)
        raise HTTPException(503, "Signal or market data is temporarily unavailable.")

    signals: dict[str, list[tuple[int, int]]] = {s: [] for s in symbols}
    for a in alerts:
        sym = str(a.get("symbol", "")).upper()
        action = str(a.get("action") or a.get("signal") or "").upper()
        t = _parse_time_ms(a.get("time") or a.get("created_at") or a.get("timestamp"))
        if sym in signals and t and t >= start_ms and action in ("BUY", "SELL"):
            signals[sym].append((t, 1 if action == "BUY" else -1))

    markets = {s: (k["open_time"], k["open"]) for s, k in zip(symbols, klines)}
    trades = []
    for s in symbols:
        trades.extend(simulate_trades(s, signals[s], *markets[s], horizon_bars, FEE, SLIPPAGE, allow_short))

    strategy = trade_metrics(trades, days)
    n_by_symbol = {s: sum(1 for t in trades if t.symbol == s) for s in symbols}
    longs = sum(1 for t in trades if t.side == 1)
    long_share = longs / len(trades) if trades else 0.5

    random_summary, beats = None, None
    if trades:
        rand = random_baseline(markets, n_by_symbol, long_share, horizon_bars, FEE, SLIPPAGE, allow_short)
        beats = float((rand < strategy["total_return"]).mean() * 100)
        random_summary = {"median_total_return": float(np.median(rand)),
                          "p5": float(np.percentile(rand, 5)), "p95": float(np.percentile(rand, 95)),
                          "simulations": len(rand)}

    bh = {s: buy_and_hold(markets[s][1], FEE, SLIPPAGE) for s in symbols}
    bh_vals = [v for v in bh.values() if v is not None]

    result = {
        "period_days": days, "horizon_minutes": horizon_minutes, "allow_short": allow_short,
        "costs": {"fee_per_side_pct": FEE * 100, "slippage_per_side_pct": SLIPPAGE * 100},
        "signals_considered": sum(len(v) for v in signals.values()),
        "strategy": strategy,
        "buy_and_hold": {"average_total_return": float(np.mean(bh_vals)) if bh_vals else None, "by_symbol": bh},
        "random": random_summary,
        "beats_random_pct": beats,
        "verdict": verdict(len(trades), beats, strategy["total_return"]),
        "notes": [
            "Entry at the next candle's open after each signal (no look-ahead); exit after the horizon.",
            "Fees and slippage are charged on both entry and exit.",
            "Overlapping trades on the same coin are skipped.",
            "Past performance does not predict future results. Not financial advice.",
        ],
        "updated_at": end_ms,
    }
    return ds.store(key, result)
