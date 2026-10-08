from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import select

from alerts.dispatcher import dispatch_events
from config.settings import get_settings
from detection.classifier import classify, confirm_timeframes
from detection.regime import detect_market_regime
from ingestion.publisher import DEAD_LETTER_STREAM, LOCAL_QUEUE, MARKET_STREAM, NEWS_STREAM, create_redis
from processing.aggregator import aggregate_candles, merge_candle_history, resample_candles
from storage.db import get_session_factory, initialize_database
from storage.models import NewsItem
from storage.repository import (
    list_candles,
    save_signal,
    upsert_candle,
)
from evaluation.stats import get_track_record_summary

logger = logging.getLogger(__name__)
GROUP = "sentinel-processors"
CONSUMER = "processor-1"


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def process_market_event(payload: dict[str, Any]) -> None:
    symbol = str(payload["symbol"]).upper()
    candle_time = _as_datetime(payload["time"])
    interval = str(payload.get("interval", "1m"))
    candle_values = {
        "open": float(payload["open"]),
        "high": float(payload["high"]),
        "low": float(payload["low"]),
        "close": float(payload["close"]),
        "volume": float(payload["volume"]),
    }
    if min(candle_values["open"], candle_values["high"], candle_values["low"], candle_values["close"]) <= 0:
        raise ValueError("Candle prices must be positive")
    if candle_values["high"] < max(candle_values["open"], candle_values["close"]):
        raise ValueError("Candle high is below open or close")
    if candle_values["low"] > min(candle_values["open"], candle_values["close"]):
        raise ValueError("Candle low is above open or close")
    if candle_values["volume"] < 0:
        raise ValueError("Candle volume cannot be negative")

    realtime_message: dict[str, Any] | None = None
    async with get_session_factory()() as session:
        async with session.begin():
            await upsert_candle(session, symbol, interval, candle_time, candle_values)
            if payload.get("historical") and not payload.get("bootstrap_latest"):
                return
            if interval != "1m":
                return
            rows = await list_candles(session, symbol, "1m", 120)
            candles = [
                {
                    "time": row.time,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                }
                for row in reversed(rows)
            ]
            features = aggregate_candles(candles)
            five_minute_rows = await list_candles(session, symbol, "5m", 120)
            seeded_five = [
                {
                    "time": row.time,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                }
                for row in reversed(five_minute_rows)
            ]
            five_minute_candles = merge_candle_history(
                seeded_five,
                resample_candles(candles, 5),
            )
            fifteen_minute_candles = await list_candles(session, symbol, "15m", 120)
            seeded_fifteen = [
                {
                    "time": row.time,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                }
                for row in reversed(fifteen_minute_candles)
            ]
            regime_candles = merge_candle_history(
                seeded_fifteen,
                resample_candles(candles, 15),
            )
            regime_info = detect_market_regime(regime_candles)
            regime = str(regime_info["regime"])
            timeframe_features = {
                "1m": features,
                "5m": aggregate_candles(five_minute_candles),
                "15m": aggregate_candles(regime_candles),
            }
            timeframe_results = {
                frame: classify(frame_features, regime)
                for frame, frame_features in timeframe_features.items()
            }
            confirmation = confirm_timeframes(timeframe_results)
            confidence = float(confirmation["confidence"])
            if regime == "HIGH_VOLATILITY":
                confidence *= get_settings().high_volatility_confidence_multiplier
            signal_values = {
                "price": features["price"],
                "change_1h": features["change_1h"],
                "rsi": features["rsi"],
                "volume_z": features["volume_z"],
                "signal": str(confirmation["signal"]),
                "confidence": confidence,
                "regime": regime,
                "timeframe_agreement": confirmation["agreement"],
                "filter_version": "mtf-v1",
                "signal_quality": str(confirmation["quality"]),
                "adx": regime_info["adx"],
                "atr_pct": regime_info["atr_pct"],
            }
            events = confirmation["events"]
            if events:
                signal_values["track_record"] = await get_track_record_summary(
                    session,
                    symbol,
                    str(events[0]["event_type"]),
                )
            else:
                signal_values["track_record"] = {
                    "hit_rate_pct": None,
                    "sample_count": 0,
                    "correct_count": 0,
                    "enough_data": False,
                }
            await save_signal(session, symbol, candle_time, signal_values)
            if not payload.get("historical"):
                features["high_volatility"] = float(regime == "HIGH_VOLATILITY")
                alerts = await dispatch_events(
                    session,
                    symbol,
                    features,
                    events,
                    regime=regime,
                    timeframe_agreement=confirmation["agreement"],
                )
                realtime_message = {
                    "type": "market_update",
                    "symbol": symbol,
                    "price": features["price"],
                    "candle": {
                        "time": candle_time.isoformat(),
                        **candle_values,
                    },
                    "candles": {
                        "1m": {"time": candle_time.isoformat(), **candle_values},
                        "5m": {
                            "time": five_minute_candles[-1]["time"].isoformat(),
                            **{key: five_minute_candles[-1][key] for key in ("open", "high", "low", "close", "volume")},
                        },
                        "15m": {
                            "time": regime_candles[-1]["time"].isoformat(),
                            **{key: regime_candles[-1][key] for key in ("open", "high", "low", "close", "volume")},
                        },
                    },
                    "signal": {"symbol": symbol, **signal_values},
                    "alerts": [
                        {
                            "id": alert.id,
                            "time": alert.time.isoformat(),
                            "symbol": alert.symbol,
                            "event_type": alert.event_type,
                            "action": alert.action,
                            "confidence": alert.confidence,
                            "price": alert.price,
                            "stop_loss": alert.stop_loss,
                            "explanation": alert.explanation,
                            "regime": alert.regime,
                            "timeframe_agreement": alert.timeframe_agreement,
                            "track_record": alert.track_record,
                            "filter_version": alert.filter_version,
                            "hit_rate_pct": None,
                            "sample_count": int(alert.track_record.get("sample_count", 0)),
                            "outcome": "pending",
                        }
                        for alert in alerts
                    ],
                }
    if realtime_message is not None:
        from api.realtime import realtime_hub

        await realtime_hub.publish(realtime_message)


async def process_news_event(payload: dict[str, Any]) -> None:
    published_at = _as_datetime(payload["published_at"]) if payload.get("published_at") else None
    async with get_session_factory()() as session:
        async with session.begin():
            existing_id = await session.scalar(select(NewsItem.id).where(NewsItem.url == str(payload["url"])))
            if existing_id is None:
                session.add(NewsItem(
                    title=str(payload["title"])[:500],
                    url=str(payload["url"])[:2000],
                    published_at=published_at,
                    summary=str(payload.get("summary", "")),
                ))


async def _create_group(redis: Redis, stream: str) -> None:
    try:
        await redis.xgroup_create(stream, GROUP, id="0", mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise


async def _handle_message(
    redis: Redis,
    stream_name: str,
    message_id: str | bytes,
    fields: dict[str | bytes, str | bytes],
) -> None:
    stream = stream_name.decode() if isinstance(stream_name, bytes) else stream_name
    normalized = {
        (key.decode() if isinstance(key, bytes) else key):
        (value.decode() if isinstance(value, bytes) else value)
        for key, value in fields.items()
    }
    try:
        payload = json.loads(normalized["payload"])
        if stream == MARKET_STREAM:
            await process_market_event(payload)
        elif stream == NEWS_STREAM:
            await process_news_event(payload)
        else:
            raise ValueError(f"Unexpected stream: {stream}")
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.exception("Failed to process %s message %s", stream, message_id)
        await redis.xadd(DEAD_LETTER_STREAM, {
            "stream": stream,
            "message_id": str(message_id),
            "payload": normalized.get("payload", ""),
            "error": str(error)[:1000],
        }, maxlen=10_000, approximate=True)
    await redis.xack(stream, GROUP, message_id)


async def consume() -> None:
    await initialize_database()
    if get_settings().redis_url == "memory://":
        logger.info("Processing events through the in-process queue")
        while True:
            stream, payload = await LOCAL_QUEUE.get()
            try:
                if stream == MARKET_STREAM:
                    await process_market_event(payload)
                elif stream == NEWS_STREAM:
                    await process_news_event(payload)
                else:
                    raise ValueError(f"Unexpected stream: {stream}")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to process local %s event", stream)
            finally:
                LOCAL_QUEUE.task_done()
        return

    redis = create_redis()
    streams = (MARKET_STREAM, NEWS_STREAM)
    try:
        for stream in streams:
            await _create_group(redis, stream)
        logger.info("Consuming streams: %s", ", ".join(streams))
        while True:
            for stream in streams:
                pending = await redis.xreadgroup(
                    GROUP, CONSUMER, {stream: "0"}, count=20
                )
                for stream_name, messages in pending:
                    for message_id, fields in messages:
                        await _handle_message(redis, stream_name, message_id, fields)
            batches = await redis.xreadgroup(
                GROUP, CONSUMER, {stream: ">" for stream in streams}, count=20, block=5000
            )
            for stream_name, messages in batches:
                for message_id, fields in messages:
                    await _handle_message(redis, stream_name, message_id, fields)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(consume())