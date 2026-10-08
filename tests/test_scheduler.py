import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jobs.scheduler import run_scheduler
from storage.models import Alert, AlertOutcome, Base, Candle
from storage.repository import delete_expired_market_data


def test_cleanup_removes_only_expired_one_minute_candles_and_alert_history():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 3, 2, tzinfo=timezone.utc)
        async with factory() as session:
            old_candle = Candle(
                symbol="BTCUSDT", interval="1m", time=now - timedelta(days=8),
                open=100, high=101, low=99, close=100, volume=1,
            )
            retained_candle = Candle(
                symbol="BTCUSDT", interval="15m", time=now - timedelta(days=8),
                open=100, high=101, low=99, close=100, volume=1,
            )
            old_alert = Alert(
                time=now - timedelta(days=91), symbol="BTCUSDT",
                event_type="breakout", action="BUY", confidence=0.8,
                price=100, stop_loss=97, explanation="Breakout",
            )
            session.add_all([old_candle, retained_candle, old_alert])
            await session.flush()
            session.add(AlertOutcome(
                alert_id=old_alert.id, horizon_minutes=60,
                checked_at=now, return_pct=0.5, hit=True,
            ))
            await session.commit()

            deleted = await delete_expired_market_data(
                session,
                now - timedelta(days=7),
                now - timedelta(days=90),
            )
            await session.commit()
            assert deleted == {"candles": 1, "outcomes": 1, "alerts": 1}
            remaining = list((await session.scalars(select(Candle))).all())
            assert len(remaining) == 1
            assert remaining[0].interval == "15m"
            assert await session.scalar(select(Alert.id)) is None
            assert await session.scalar(select(AlertOutcome.id)) is None
        await engine.dispose()

    asyncio.run(run())


def test_scheduler_rejects_an_unreasonable_poll_interval():
    with pytest.raises(ValueError, match="at least 60"):
        asyncio.run(run_scheduler(interval_seconds=59))
