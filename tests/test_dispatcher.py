import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alerts.dispatcher import dispatch_events
from storage.models import Alert, Base


def test_dispatched_alert_persists_regime_timeframe_and_track_record():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        agreement = {"1m": True, "5m": True, "15m": False}
        async with factory() as session:
            alerts = await dispatch_events(
                session,
                "BTCUSDT",
                {"price": 100.0, "high_volatility": 1.0},
                [{"event_type": "breakout", "confidence": 0.95}],
                regime="HIGH_VOLATILITY",
                timeframe_agreement=agreement,
            )
            await session.commit()
            persisted = await session.get(Alert, alerts[0].id)
            assert persisted is not None
            assert persisted.regime == "HIGH_VOLATILITY"
            assert persisted.timeframe_agreement == agreement
            assert persisted.track_record == {
                "hit_rate_pct": None,
                "sample_count": 0,
                "correct_count": 0,
                "enough_data": False,
            }
            assert "Volatility is elevated" in persisted.explanation
            assert persisted.confidence < 0.95
            assert persisted.stop_loss < 97
        await engine.dispose()

    asyncio.run(run())
