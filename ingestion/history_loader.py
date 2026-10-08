from __future__ import annotations

import logging

import httpx

from config.settings import get_settings
from ingestion.publisher import publish_candle

logger = logging.getLogger(__name__)
DEFAULT_HISTORY_LIMIT = 120


async def load_recent_candles(
    symbols: list[str],
    interval: str,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> None:
    if interval not in {"1m", "5m", "15m"}:
        raise ValueError("interval must be 1m, 5m, or 15m")
    if limit < 1 or limit > 1000:
        raise ValueError("history limit must be between 1 and 1000")

    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        for symbol in symbols:
            try:
                response = await client.get(
                    f"{settings.binance_rest_url}/api/v3/klines",
                    params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
                )
                response.raise_for_status()
                rows = response.json()
                for index, row in enumerate(rows):
                    await publish_candle({
                        "symbol": symbol.upper(),
                        "interval": interval,
                        "time": row[0],
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                        "historical": True,
                        "bootstrap_latest": index == len(rows) - 1,
                    })
                logger.info(
                    "Queued %d recent %s candles for %s",
                    len(rows),
                    interval,
                    symbol.upper(),
                )
            except (httpx.HTTPError, ValueError, IndexError, KeyError, TypeError):
                logger.exception("Could not seed recent Binance candles for %s", symbol.upper())
