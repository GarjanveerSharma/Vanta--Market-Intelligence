from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import Alert, AlertOutcome

MIN_TRACK_RECORD_SAMPLES = 10
TRACK_RECORD_DAYS = 30


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def get_track_record_stats(
    session: AsyncSession,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    cutoff = _as_utc(now or datetime.now(timezone.utc)) - timedelta(days=TRACK_RECORD_DAYS)
    rows = (await session.execute(
        select(
            Alert.symbol,
            Alert.event_type,
            Alert.regime,
            Alert.filter_version,
            AlertOutcome.hit,
        )
        .join(AlertOutcome, AlertOutcome.alert_id == Alert.id)
        .where(
            Alert.time >= cutoff,
            AlertOutcome.horizon_minutes == 60,
            AlertOutcome.hit.is_not(None),
        )
    )).all()
    grouped: dict[tuple[str, str, str, str], list[bool]] = defaultdict(list)
    for symbol, event_type, regime, filter_version, hit in rows:
        grouped[(symbol, event_type, regime, filter_version)].append(bool(hit))

    results: list[dict[str, object]] = []
    for (symbol, event_type, regime, filter_version), samples in sorted(grouped.items()):
        enough_data = len(samples) >= MIN_TRACK_RECORD_SAMPLES
        results.append({
            "symbol": symbol,
            "event_type": event_type,
            "regime": regime,
            "filter_version": filter_version,
            "hit_rate_pct": round(sum(samples) * 100 / len(samples), 2) if enough_data else None,
            "sample_count": len(samples),
            "correct_count": sum(samples),
            "enough_data": enough_data,
        })
    return results


async def get_track_record_summary(
    session: AsyncSession,
    symbol: str,
    event_type: str,
    now: datetime | None = None,
) -> dict[str, object]:
    groups = await get_track_record_stats(session, now)
    samples = [
        group for group in groups
        if group["symbol"] == symbol and group["event_type"] == event_type
    ]
    sample_count = sum(int(group["sample_count"]) for group in samples)
    correct_count = sum(int(group["correct_count"]) for group in samples)
    enough_data = sample_count >= MIN_TRACK_RECORD_SAMPLES
    return {
        "hit_rate_pct": round(correct_count * 100 / sample_count, 2) if enough_data else None,
        "sample_count": sample_count,
        "correct_count": correct_count,
        "enough_data": enough_data,
    }
