"""Where the insights get their data.

- Candles: Binance public REST API (no key needed).
- Alerts: Vanta's own GET /alerts endpoint, so this module doesn't depend on
  how the database layer is written.
"""
import os
import time
from typing import Any

import httpx
import numpy as np

BINANCE_REST_URL = os.getenv("BINANCE_REST_URL", "https://data-api.binance.vision/api/v3")
INTERNAL_API_URL = os.getenv("INTERNAL_API_URL") or f"http://127.0.0.1:{os.getenv('PORT', '8000')}"
SYMBOLS = [s.strip() for s in os.getenv("INSIGHT_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT").split(",") if s.strip()]
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000}
TIMEOUT = httpx.Timeout(10.0)

_cache: dict[tuple, tuple[float, Any]] = {}


def cached(key: tuple, ttl: float):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    return None


def store(key: tuple, value: Any):
    if len(_cache) > 500:
        _cache.clear()
    _cache[key] = (time.time(), value)
    return value


def _to_arrays(rows: list) -> dict[str, np.ndarray]:
    if not rows:
        empty = np.array([], dtype=float)
        return {k: empty for k in ("open_time", "open", "high", "low", "close", "volume")}
    arr = np.array([[float(r[i]) for i in range(6)] for r in rows])
    return {
        "open_time": arr[:, 0].astype(np.int64),
        "open": arr[:, 1], "high": arr[:, 2], "low": arr[:, 3],
        "close": arr[:, 4], "volume": arr[:, 5],
    }


async def fetch_klines(symbol: str, interval: str, limit: int = 300, end_time_ms: int | None = None) -> dict[str, np.ndarray]:
    key = ("klines", symbol, interval, limit, end_time_ms)
    if (hit := cached(key, 20)) is not None:
        return hit
    params = {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
    if end_time_ms:
        params["endTime"] = end_time_ms
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{BINANCE_REST_URL}/klines", params=params)
        r.raise_for_status()
    return store(key, _to_arrays(r.json()))


async def fetch_klines_range(symbol: str, interval: str, start_ms: int, end_ms: int) -> dict[str, np.ndarray]:
    """All candles between start and end, paginating 1000 at a time."""
    key = ("range", symbol, interval, start_ms // 60_000, end_ms // 60_000)
    if (hit := cached(key, 120)) is not None:
        return hit
    rows, cursor = [], start_ms
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        while cursor < end_ms and len(rows) < 20_000:
            r = await client.get(f"{BINANCE_REST_URL}/klines", params={
                "symbol": symbol, "interval": interval, "startTime": cursor, "endTime": end_ms, "limit": 1000})
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            rows.extend(batch)
            cursor = int(batch[-1][0]) + INTERVAL_MS[interval]
            if len(batch) < 1000:
                break
    return store(key, _to_arrays(rows))


async def fetch_alerts(symbol: str | None = None, limit: int = 1000) -> list[dict]:
    key = ("alerts", symbol, limit)
    if (hit := cached(key, 60)) is not None:
        return hit
    params: dict[str, Any] = {"limit": limit}
    if symbol:
        params["symbol"] = symbol
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{INTERNAL_API_URL}/alerts", params=params)
        r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):  # tolerate {"items": [...]} style responses
        data = data.get("items") or data.get("alerts") or []
    return store(key, data)
