from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from evaluation.calibration import calibrate_rules
from evaluation.outcome_tracker import evaluate_due_outcomes
from sqlalchemy import select
from api.realtime import realtime_hub
from storage.db import get_session_factory
from storage.models import Alert, AlertOutcome
from storage.repository import delete_expired_market_data

logger = logging.getLogger(__name__)


async def run_scheduler(interval_seconds: int = 300) -> None:
    if interval_seconds < 60:
        raise ValueError("scheduler interval must be at least 60 seconds")
    next_cleanup: datetime | None = None
    while True:
        now = datetime.now(timezone.utc)
        try:
            async with get_session_factory()() as session:
                async with session.begin():
                    outcomes = await evaluate_due_outcomes(session, now)
                    changes = await calibrate_rules(session, now)
                    if next_cleanup is None or now >= next_cleanup:
                        deleted = await delete_expired_market_data(
                            session,
                            now - timedelta(days=7),
                            now - timedelta(days=90),
                        )
                        next_cleanup = now + timedelta(days=1)
                    else:
                        deleted = {"candles": 0, "outcomes": 0, "alerts": 0}
            if outcomes or changes or any(deleted.values()):
                logger.info(
                    "Scheduled jobs evaluated %d outcomes, calibrated %d rules, "
                    "and removed %s",
                    outcomes,
                    len(changes),
                    deleted,
                )
            if outcomes:
                async with get_session_factory()() as session:
                    outcome_rows = (await session.execute(
                        select(AlertOutcome.alert_id, Alert.symbol, AlertOutcome.hit)
                        .join(Alert, Alert.id == AlertOutcome.alert_id)
                        .where(
                            AlertOutcome.horizon_minutes == 60,
                            AlertOutcome.checked_at >= now - timedelta(seconds=1),
                            AlertOutcome.checked_at <= now + timedelta(seconds=1),
                        )
                    )).all()
                for alert_id, symbol, hit in outcome_rows:
                    await realtime_hub.publish({
                        "type": "alert_outcome",
                        "symbol": symbol,
                        "outcomes": [{
                            "alert_id": alert_id,
                            "outcome": "pending" if hit is None else "correct" if hit else "wrong",
                        }],
                    })
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled market-evaluation job failed")
        await asyncio.sleep(interval_seconds)
