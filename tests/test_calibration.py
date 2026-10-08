import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alerts.track_record import calibrate_rules
from config.settings import get_settings
from storage.models import Alert, AlertOutcome, Base, CalibrationLog, RuleCalibration, RuntimeSetting


def test_calibration_is_bounded_and_logs_the_threshold_change():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 3, 2, tzinfo=timezone.utc)
        async with factory() as session:
            session.add(RuntimeSetting(key="calibration_enabled", value=True))
            for index in range(20):
                alert = Alert(
                    time=now - timedelta(days=2, minutes=index),
                    symbol="BTCUSDT",
                    event_type="pump",
                    action="SELL",
                    confidence=0.7,
                    price=100,
                    stop_loss=103,
                    explanation="Pump",
                )
                session.add(alert)
                await session.flush()
                session.add(AlertOutcome(
                    alert_id=alert.id,
                    horizon_minutes=60,
                    checked_at=now,
                    return_pct=1,
                    hit=False,
                ))
            await session.commit()

            changes = await calibrate_rules(session, now)
            await session.commit()
            settings = get_settings()
            change = changes[0]
            assert change.new_threshold <= settings.calibration_confidence_max
            assert change.new_threshold >= settings.calibration_confidence_min
            assert change.new_threshold > change.old_threshold
            assert change.sample_count == 20
            assert await session.get(RuleCalibration, "pump") is not None
            persisted = list((await session.scalars(select(CalibrationLog))).all())
            assert len(persisted) == 1
            assert "below" in persisted[0].reason
        await engine.dispose()

    asyncio.run(run())
