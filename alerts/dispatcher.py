from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from advisor.signal_mapper import map_event
from config.settings import get_settings
from evaluation.stats import get_track_record_summary
from storage.models import Alert, RuleCalibration
from storage.repository import save_alert

async def dispatch_events(
    session: AsyncSession,
    symbol: str,
    features: dict[str, float],
    events: list[dict[str, object]],
    regime: str = "SIDEWAYS",
    timeframe_agreement: dict[str, bool] | None = None,
) -> list[Alert]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    created: list[Alert] = []
    cooldown_seconds = settings.alert_cooldown_seconds
    confidence_threshold = settings.alert_confidence_threshold
    for event in events:
        confidence = float(event["confidence"])
        event_type = str(event["event_type"])
        rule_calibration = await session.get(RuleCalibration, event_type)
        effective_threshold = (
            rule_calibration.min_confidence if rule_calibration else confidence_threshold
        )
        if confidence < effective_threshold:
            continue
        recent = await session.scalar(
            select(Alert.id)
            .where(
                Alert.symbol == symbol,
                Alert.event_type == event_type,
                Alert.time >= now - timedelta(seconds=cooldown_seconds),
            )
            .limit(1)
        )
        if recent is not None:
            continue
        high_volatility = regime == "HIGH_VOLATILITY"
        mapped = map_event(
            event,
            features["price"],
            "medium",
            high_volatility=high_volatility,
            stop_multiplier=settings.high_volatility_stop_multiplier,
            confidence_multiplier=settings.high_volatility_confidence_multiplier,
            regime=regime,
        )
        track_record = await get_track_record_summary(session, symbol, event_type)
        alert = Alert(
            time=now,
            symbol=symbol,
            event_type=event_type,
            action=str(mapped["action"]),
            confidence=float(mapped["confidence"]),
            price=features["price"],
            stop_loss=float(mapped["stop_loss"]),
            explanation=str(mapped["explanation"]),
            regime=regime,
            timeframe_agreement=timeframe_agreement or {},
            track_record=track_record,
            filter_version="mtf-v1",
        )
        save_alert(session, alert)
        created.append(alert)
    await session.flush()
    return created