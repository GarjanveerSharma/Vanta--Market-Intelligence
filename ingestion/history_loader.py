from __future__ import annotations

import logging

import httpx

from config.settings import get_settings
from ingestion.publisher import publish_candle

logger = logging.getLogger(__name__)
DEFAULT_HISTORY_LIMIT = 120
FALLBACK_REST_URL = "https://data-api.binance.vision"


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
    base_urls = list(dict.fromkeys((
        settings.binance_rest_url.rstrip("/"),
        FALLBACK_REST_URL,
    )))
    async with httpx.AsyncClient(timeout=15) as client:
        for symbol in symbols:
            rows = None
            try:
                for base_url in base_urls:
                    try:
                        response = await client.get(
                            f"{base_url}/api/v3/klines",
                            params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
                        )
                        response.raise_for_status()
                        rows = response.json()
                        break
                    except httpx.HTTPError as error:
                        logger.warning(
                            "History request failed for %s via %s: %s",
                            symbol.upper(),
                            base_url,
                            error,
                        )
                if rows is None:
                    logger.error(
                        "Could not load %s candle history for %s from any Binance REST endpoint",
                        interval,
                        symbol.upper(),
                    )
                    continue
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
            except (ValueError, IndexError, KeyError, TypeError):
                logger.exception("Could not parse recent Binance candles for %s", symbol.upper())


async def load_latest_candles(symbols: list[str], interval: str) -> int:
    if interval not in {"1m", "5m", "15m"}:
        raise ValueError("interval must be 1m, 5m, or 15m")

    settings = get_settings()
    base_urls = list(dict.fromkeys((
        settings.binance_rest_url.rstrip("/"),
        FALLBACK_REST_URL,
    )))
    published = 0
    async with httpx.AsyncClient(timeout=15) as client:
        for symbol in symbols:
            last_error: Exception | None = None
            for base_url in base_urls:
                try:
                    response = await client.get(
                        f"{base_url}/api/v3/klines",
                        params={"symbol": symbol.upper(), "interval": interval, "limit": 2},
                    )
                    response.raise_for_status()
                    rows = response.json()
                    row = rows[-1]
                    await publish_candle({
                        "symbol": symbol.upper(),
                        "interval": interval,
                        "time": row[0],
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                    })
                    published += 1
                    break
                except (httpx.HTTPError, ValueError, IndexError, KeyError, TypeError) as error:
                    last_error = error
            else:
                logger.warning(
                    "Could not poll Binance REST candles for %s after trying %s: %s",
                    symbol.upper(),
                    ", ".join(base_urls),
                    last_error,
                )
    return published
