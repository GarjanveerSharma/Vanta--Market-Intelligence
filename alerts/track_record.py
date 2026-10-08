from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from detection.rules import EVENTS
from storage.models import (
    Alert,
    AlertOutcome,
    CalibrationChange,
    Candle,
    RuleCalibration,
    RuntimeSetting,
)
from storage.repository import add_alert_outcome

HORIZONS_MINUTES = (15, 30, 60)
CALIBRATION_ENABLED_KEY = "calibration_enabled"
LAST_CALIBRATION_KEY = "last_calibration_at"
PREDICTION_DIRECTION = {"BUY": 1, "SELL": -1, "AVOID": -1}


def expected_outcome(
    entry_price: float,
    exit_price: float,
    action: str,
    threshold_pct: float,
) -> tuple[float, bool | None]:
    if entry_price <= 0 or threshold_pct <= 0:
        raise ValueError("entry price and outcome threshold must be positive")
    return_pct = (exit_price / entry_price - 1.0) * 100.0
    direction = PREDICTION_DIRECTION.get(action)
    if direction is None:
        return return_pct, None
    hit = return_pct * direction > threshold_pct
    return return_pct, hit


def tighten_threshold(
    current: float,
    step: float,
    minimum: float,
    maximum: float,
) -> float:
    if step <= 0 or minimum < 0 or maximum < minimum:
        raise ValueError("invalid calibration threshold bounds")
    return min(maximum, max(minimum, current + step))


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def evaluate_due_outcomes(
    session: AsyncSession,
    now: datetime | None = None,
) -> int:
    settings = get_settings()
    checked_at = _utc(now or datetime.now(timezone.utc))
    outcomes_per_alert = (
        select(func.count(AlertOutcome.id))
        .where(AlertOutcome.alert_id == Alert.id)
        .correlate(Alert)
        .scalar_subquery()
    )
    alerts = list((await session.scalars(
        select(Alert)
        .where(
            Alert.time <= checked_at - timedelta(minutes=min(HORIZONS_MINUTES)),
            outcomes_per_alert < len(HORIZONS_MINUTES),
        )
        .order_by(Alert.time)
        .limit(5000)
    )).all())
    added = 0
    for alert in alerts:
        alert_time = _utc(alert.time)
        for horizon in HORIZONS_MINUTES:
            target_time = alert_time + timedelta(minutes=horizon)
            if target_time > checked_at:
                continue
            already_checked = await session.scalar(
                select(AlertOutcome.id).where(
                    AlertOutcome.alert_id == alert.id,
                    AlertOutcome.horizon_minutes == horizon,
                )
            )
            if already_checked is not None:
                continue
            candle = await session.scalar(
                select(Candle)
                .where(
                    Candle.symbol == alert.symbol,
                    Candle.interval == "1m",
                    Candle.time >= target_time,
                    Candle.time <= target_time + timedelta(minutes=2),
                )
                .order_by(Candle.time)
                .limit(1)
            )
            if candle is None:
                continue
            return_pct, hit = expected_outcome(
                alert.price,
                candle.close,
                alert.action,
                settings.outcome_move_threshold_pct,
            )
            add_alert_outcome(session, AlertOutcome(
                alert_id=alert.id,
                horizon_minutes=horizon,
                checked_at=checked_at,
                return_pct=return_pct,
                hit=hit,
            ))
            added += 1
    if added:
        await session.flush()
    return added


async def get_track_record(session: AsyncSession) -> list[dict[str, object]]:
    rows = (await session.execute(
        select(
            Alert.symbol,
            Alert.event_type,
            Alert.regime,
            Alert.filter_version,
            AlertOutcome.hit,
        )
        .join(AlertOutcome, AlertOutcome.alert_id == Alert.id)
        .where(AlertOutcome.horizon_minutes == 60, AlertOutcome.hit.is_not(None))
    )).all()
    grouped: dict[tuple[str, str, str, str], list[bool]] = defaultdict(list)
    for symbol, event_type, regime, filter_version, hit in rows:
        grouped[(symbol, event_type, regime, filter_version)].append(bool(hit))
    return [
        {
            "symbol": symbol,
            "event_type": event_type,
            "regime": regime,
            "filter_version": filter_version,
            "hit_rate_pct": round(sum(results) * 100.0 / len(results), 2),
            "sample_count": len(results),
            "correct_count": sum(results),
        }
        for (symbol, event_type, regime, filter_version), results in sorted(grouped.items())
    ]


async def calibrate_rules(
    session: AsyncSession,
    now: datetime | None = None,
) -> list[CalibrationChange]:
    settings = get_settings()
    calibrated_at = _utc(now or datetime.now(timezone.utc))
    enabled = await session.get(RuntimeSetting, CALIBRATION_ENABLED_KEY)
    if enabled is None:
        enabled = RuntimeSetting(key=CALIBRATION_ENABLED_KEY, value=True)
        session.add(enabled)
        await session.flush()
    if not bool(enabled.value):
        return []

    last_run = await session.get(RuntimeSetting, LAST_CALIBRATION_KEY)
    if last_run is not None:
        last_at = _utc(datetime.fromisoformat(last_run.value))
        if calibrated_at - last_at < timedelta(days=1):
            return []

    rows = (await session.execute(
        select(Alert.event_type, AlertOutcome.hit)
        .join(AlertOutcome, AlertOutcome.alert_id == Alert.id)
        .where(
            Alert.time >= calibrated_at - timedelta(days=30),
            AlertOutcome.horizon_minutes == 60,
            AlertOutcome.hit.is_not(None),
        )
    )).all()
    counts: dict[str, list[bool]] = defaultdict(list)
    for event_type, hit in rows:
        counts[event_type].append(bool(hit))

    changes: list[CalibrationChange] = []
    for event_type in EVENTS:
        results = counts[event_type]
        if len(results) < settings.calibration_min_samples:
            continue
        hit_rate = sum(results) * 100.0 / len(results)
        if hit_rate >= settings.calibration_low_hit_rate_pct:
            continue
        calibration = await session.get(RuleCalibration, event_type)
        current = calibration.min_confidence if calibration else settings.alert_confidence_threshold
        updated = tighten_threshold(
            current,
            settings.calibration_confidence_step,
            settings.calibration_confidence_min,
            settings.calibration_confidence_max,
        )
        if updated <= current:
            continue
        if calibration is None:
            calibration = RuleCalibration(event_type=event_type, min_confidence=updated)
            session.add(calibration)
        else:
            calibration.min_confidence = updated
        change = CalibrationChange(
            changed_at=calibrated_at,
            event_type=event_type,
            old_threshold=current,
            new_threshold=updated,
            hit_rate_pct=hit_rate,
            sample_count=len(results),
            reason=(
                f"60-minute hit rate {hit_rate:.1f}% was below "
                f"{settings.calibration_low_hit_rate_pct:.1f}% across {len(results)} signals"
            ),
        )
        session.add(change)
        changes.append(change)

    if last_run is None:
        session.add(RuntimeSetting(key=LAST_CALIBRATION_KEY, value=calibrated_at.isoformat()))
    else:
        last_run.value = calibrated_at.isoformat()
    await session.flush()
    return changes
