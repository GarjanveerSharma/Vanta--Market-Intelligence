from __future__ import annotations

import json
import asyncio
from typing import Any

from redis.asyncio import Redis

from config.settings import get_settings

MARKET_STREAM = "sentinel:market"
NEWS_STREAM = "sentinel:news"
DEAD_LETTER_STREAM = "sentinel:dead-letter"
LOCAL_QUEUE: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=10_000)


def create_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def publish(stream: str, event: dict[str, Any], redis: Redis | None = None) -> str:
    if get_settings().redis_url == "memory://":
        await LOCAL_QUEUE.put((stream, event))
        return str(LOCAL_QUEUE.qsize())
    client = redis or create_redis()
    try:
        fields = {"payload": json.dumps(event, separators=(",", ":"))}
        return str(await client.xadd(stream, fields, maxlen=100_000, approximate=True))
    finally:
        if redis is None:
            await client.aclose()


async def publish_candle(event: dict[str, Any], redis: Redis | None = None) -> str:
    return await publish(MARKET_STREAM, event, redis)


async def publish_news(event: dict[str, Any], redis: Redis | None = None) -> str:
    return await publish(NEWS_STREAM, event, redis)