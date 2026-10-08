import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evaluation.stats import get_track_record_stats
from storage.models import Alert, AlertOutcome, Base


def test_track_record_stats_use_30_days_and_hide_rates_below_ten_samples():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 4, 2, tzinfo=timezone.utc)
        async with factory() as session:
            for index in range(10):
                alert = Alert(
                    time=now - timedelta(days=1, minutes=index),
                    symbol="BTCUSDT",
                    event_type="breakout",
                    action="BUY",
                    confidence=0.8,
                    price=100,
                    stop_loss=97,
                    explanation="Breakout",
                    regime="TRENDING_UP",
                    filter_version="mtf-v1",
                )
                session.add(alert)
                await session.flush()
                session.add(AlertOutcome(
                    alert_id=alert.id,
                    horizon_minutes=60,
                    checked_at=now,
                    return_pct=0.5,
                    hit=index < 6,
                ))
            old_alert = Alert(
                time=now - timedelta(days=31),
                symbol="BTCUSDT",
                event_type="breakout",
                action="BUY",
                confidence=0.8,
                price=100,
                stop_loss=97,
                explanation="Old signal",
                regime="SIDEWAYS",
                filter_version="legacy-v0",
            )
            session.add(old_alert)
            await session.flush()
            session.add(AlertOutcome(
                alert_id=old_alert.id,
                horizon_minutes=60,
                checked_at=now,
                return_pct=0.5,
                hit=True,
            ))
            await session.commit()

            groups = await get_track_record_stats(session, now)
            assert len(groups) == 1
            assert groups[0]["sample_count"] == 10
            assert groups[0]["hit_rate_pct"] == 60
            assert groups[0]["enough_data"] is True
        await engine.dispose()

    asyncio.run(run())
