from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import Integer, cast, func, select

from api.schemas import AlertOut
from api.deps import SessionDep
from storage.models import Alert, AlertOutcome
from storage.repository import list_alerts as repository_list_alerts

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    session: SessionDep,
    symbol: str | None = None,
    event_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, object]]:
    alerts = await repository_list_alerts(session, symbol, event_type, limit)
    outcome_rows = (await session.execute(
        select(
            Alert.symbol,
            Alert.event_type,
            func.count(AlertOutcome.id),
            func.sum(cast(AlertOutcome.hit, Integer)),
        )
        .join(AlertOutcome, AlertOutcome.alert_id == Alert.id)
        .where(
            AlertOutcome.horizon_minutes == 60,
            AlertOutcome.hit.is_not(None),
        )
        .group_by(Alert.symbol, Alert.event_type)
    )).all()
    grouped = {
        (symbol, event_type): (int(samples), int(correct or 0))
        for symbol, event_type, samples, correct in outcome_rows
    }
    outcomes = dict((await session.execute(
        select(AlertOutcome.alert_id, AlertOutcome.hit)
        .join(Alert, Alert.id == AlertOutcome.alert_id)
        .where(
            Alert.id.in_([alert.id for alert in alerts]),
            AlertOutcome.horizon_minutes == 60,
        )
    )).all()) if alerts else {}
    results: list[dict[str, object]] = []
    for alert in alerts:
        sample_count, correct_count = grouped.get((alert.symbol, alert.event_type), (0, 0))
        hit_rate = (
            round(correct_count * 100.0 / sample_count, 2)
            if sample_count >= 10 else None
        )
        results.append({
            "id": alert.id,
            "time": alert.time,
            "symbol": alert.symbol,
            "event_type": alert.event_type,
            "action": alert.action,
            "confidence": alert.confidence,
            "price": alert.price,
            "stop_loss": alert.stop_loss,
            "explanation": alert.explanation,
            "regime": alert.regime,
            "filter_version": alert.filter_version,
            "timeframe_agreement": alert.timeframe_agreement,
            "track_record": alert.track_record,
            "hit_rate_pct": hit_rate,
            "sample_count": sample_count,
            "outcome": (
                "pending" if outcomes.get(alert.id) is None
                else "correct" if outcomes[alert.id] else "wrong"
            ),
        })
    return results