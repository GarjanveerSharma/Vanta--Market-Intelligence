from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import urlencode

import httpx
import yaml
from websockets.asyncio.client import connect

from config.settings import get_settings
from ingestion.history_loader import load_recent_candles
from ingestion.news_fetcher import run_news_fetcher
from ingestion.publisher import publish_candle

logger = logging.getLogger(__name__)
HISTORY_LIMIT = 120


def load_symbols(path: str) -> list[str]:
    with open(path, encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    symbols = [str(symbol).strip().lower() for symbol in config.get("symbols", [])]
    if not symbols or any(not symbol.isalnum() for symbol in symbols):
        raise ValueError("coins config must contain valid Binance symbols")
    return symbols


def websocket_url(base_url: str, symbols: list[str], interval: str = "1m") -> str:
    streams = "/".join(f"{symbol}@kline_{interval}" for symbol in symbols)
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'streams': streams})}"


async def seed_recent_candles(symbols: list[str], interval: str) -> None:
    await load_recent_candles(symbols, interval, HISTORY_LIMIT)


async def consume_market_data() -> None:
    settings = get_settings()
    symbols = load_symbols(settings.coins_config)
    with open(settings.coins_config, encoding="utf-8") as file:
        interval = (yaml.safe_load(file) or {}).get("interval", "1m")
    url = websocket_url(settings.binance_ws_url, symbols, interval)
    await seed_recent_candles(symbols, interval)
    delay = 1
    while True:
        try:
            async with connect(url, ping_interval=20, ping_timeout=20, max_size=2**20) as socket:
                logger.info("Connected to Binance streams for %s", ", ".join(symbols))
                delay = 1
                async for raw in socket:
                    message = json.loads(raw)
                    data = message.get("data", {})
                    kline = data.get("k")
                    if not kline:
                        continue
                    candle = {
                        "symbol": kline["s"],
                        "interval": kline["i"],
                        "time": kline["t"],
                        "open": float(kline["o"]),
                        "high": float(kline["h"]),
                        "low": float(kline["l"]),
                        "close": float(kline["c"]),
                        "volume": float(kline["v"]),
                    }
                    await publish_candle(candle)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Binance websocket failed; reconnecting in %s seconds", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)


async def run() -> None:
    settings = get_settings()
    symbols = load_symbols(settings.coins_config)
    await seed_recent_candles(symbols, "15m")
    await seed_recent_candles(symbols, "5m")
    await asyncio.gather(consume_market_data(), run_news_fetcher())


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(run())