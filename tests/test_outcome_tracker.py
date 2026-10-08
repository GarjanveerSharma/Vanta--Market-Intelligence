import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evaluation.outcome_tracker import evaluate_due_outcomes, expected_outcome
from storage.models import Alert, AlertOutcome, Base, Candle


def test_outcome_tracker_checks_15_30_and_60_minute_horizons_once():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 3, 2, 1, 0, tzinfo=timezone.utc)
        alert_time = now - timedelta(minutes=61)
        async with factory() as session:
            alert = Alert(
                time=alert_time,
                symbol="BTCUSDT",
                event_type="breakout",
                action="BUY",
                confidence=0.8,
                price=100,
                stop_loss=97,
                explanation="Breakout",
            )
            session.add(alert)
            await session.flush()
            for horizon, close in ((15, 100.4), (30, 99.0), (60, 100.5)):
                session.add(Candle(
                    symbol="BTCUSDT",
                    interval="1m",
                    time=alert_time + timedelta(minutes=horizon),
                    open=100,
                    high=max(100, close),
                    low=min(100, close),
                    close=close,
                    volume=1,
                ))
            await session.commit()

            assert await evaluate_due_outcomes(session, now) == 3
            await session.commit()
            outcomes = list((await session.scalars(
                select(AlertOutcome).order_by(AlertOutcome.horizon_minutes)
            )).all())
            assert [row.horizon_minutes for row in outcomes] == [15, 30, 60]
            assert [row.hit for row in outcomes] == [True, False, True]
            assert await evaluate_due_outcomes(session, now) == 0
        await engine.dispose()

    assert expected_outcome(100, 100.31, "BUY", 0.3)[1] is True
    asyncio.run(run())
