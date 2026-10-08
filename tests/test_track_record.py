import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alerts.track_record import calibrate_rules, evaluate_due_outcomes, expected_outcome, tighten_threshold
from alerts.track_record import get_track_record
from api.routes.alerts import list_alerts
from config.settings import get_settings
from processing.aggregator import merge_candle_history, resample_candles
from storage.db import close_database, get_engine, get_session_factory
from storage.models import Alert, AlertOutcome, Base, Candle, RuleCalibration, RuntimeSetting, Signal
from processing.consumer import process_market_event


def test_outcome_requires_threshold_move_in_predicted_direction():
    assert expected_outcome(100.0, 100.31, "BUY", 0.3) == pytest.approx((0.31, True))
    assert expected_outcome(100.0, 99.69, "SELL", 0.3) == pytest.approx((-0.31, True))
    assert expected_outcome(100.0, 100.31, "SELL", 0.3) == pytest.approx((0.31, False))
    assert expected_outcome(100.0, 101.0, "HOLD", 0.3) == pytest.approx((1.0, None))


def test_tightening_stays_inside_configured_bounds():
    assert tighten_threshold(0.6, 0.05, 0.55, 0.7) == pytest.approx(0.65)
    assert tighten_threshold(0.69, 0.05, 0.55, 0.7) == pytest.approx(0.7)
    assert tighten_threshold(0.7, 0.05, 0.55, 0.7) == pytest.approx(0.7)
    with pytest.raises(ValueError):
        tighten_threshold(0.6, 0, 0.55, 0.7)


def test_track_record_and_alert_cards_group_samples_and_filter_version():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        async with factory() as session:
            for index in range(20):
                filtered = index >= 10
                alert = Alert(
                    time=now - timedelta(hours=index + 2),
                    symbol="BTCUSDT",
                    event_type="breakout",
                    action="BUY",
                    confidence=0.8,
                    price=100,
                    stop_loss=97,
                    explanation="Breakout",
                    regime="TRENDING_UP" if filtered else "SIDEWAYS",
                    filter_version="mtf-v1" if filtered else "legacy-v0",
                )
                session.add(alert)
                await session.flush()
                session.add(AlertOutcome(
                    alert_id=alert.id,
                    horizon_minutes=60,
                    checked_at=now,
                    return_pct=1.0 if index % 2 else -1.0,
                    hit=index % 2 == 1,
                ))
            await session.commit()
            groups = await get_track_record(session)
            assert len(groups) == 2
            assert {group["filter_version"] for group in groups} == {"legacy-v0", "mtf-v1"}
            alerts = await list_alerts(session, limit=100)
            assert len(alerts) == 20
            assert all(alert["sample_count"] == 20 for alert in alerts)
            assert all(alert["hit_rate_pct"] == 50 for alert in alerts)
        await engine.dispose()

    asyncio.run(run())


def test_five_minute_resampling_preserves_ohlcv():
    candles = [
        {
            "time": datetime(2026, 1, 1, 0, index, tzinfo=timezone.utc),
            "open": 100 + index,
            "high": 101 + index,
            "low": 99 + index,
            "close": 100.5 + index,
            "volume": 10,
        }
        for index in range(10)
    ]
    bars = resample_candles(candles, 5)
    assert len(bars) == 2
    assert bars[0]["open"] == 100
    assert bars[0]["close"] == 104.5
    assert bars[0]["high"] == 105
    assert bars[0]["low"] == 99
    assert bars[0]["volume"] == 50


def test_live_resampled_bars_override_seeded_bars_with_matching_timestamp():
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    seeded = [{
        "time": stamp,
        "open": 100,
        "high": 110,
        "low": 90,
        "close": 100,
        "volume": 50,
    }]
    live = [{
        "time": stamp.isoformat(),
        "open": 101,
        "high": 105,
        "low": 99,
        "close": 104,
        "volume": 10,
    }]
    assert merge_candle_history(seeded, live) == live


def test_live_processor_persists_regime_and_three_timeframe_agreement(monkeypatch):
    async def run(database_path):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
        monkeypatch.setenv("REDIS_URL", "memory://")
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        engine = get_engine()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with get_session_factory()() as session:
            session.add_all([
                Candle(
                    symbol="BTCUSDT",
                    interval="1m",
                    time=now - timedelta(minutes=index),
                    open=100 + index * 0.01,
                    high=100.1 + index * 0.01,
                    low=99.9 + index * 0.01,
                    close=100 + index * 0.01,
                    volume=100,
                )
                for index in reversed(range(120))
            ])
            session.add_all([
                Candle(
                    symbol="BTCUSDT",
                    interval="15m",
                    time=now - timedelta(minutes=15 * index),
                    open=100 + index,
                    high=101 + index,
                    low=99.5 + index,
                    close=100.5 + index,
                    volume=1000,
                )
                for index in reversed(range(60))
            ])
            await session.commit()
        await process_market_event({
            "symbol": "BTCUSDT",
            "interval": "1m",
            "time": int(now.timestamp() * 1000),
            "open": 100,
            "high": 100.2,
            "low": 99.8,
            "close": 100.1,
            "volume": 100,
        })
        async with get_session_factory()() as session:
            signal = await session.scalar(select(Signal).where(Signal.symbol == "BTCUSDT"))
            assert signal is not None
            assert signal.regime in {"TRENDING_UP", "TRENDING_DOWN", "SIDEWAYS", "HIGH_VOLATILITY"}
            assert set(signal.timeframe_agreement) == {"1m", "5m", "15m"}
            assert signal.signal_quality in {"confirmed", "partial", "unconfirmed"}
            assert signal.adx is not None
            assert signal.atr_pct is not None
        await close_database()
        get_settings.cache_clear()

    with tempfile.TemporaryDirectory() as directory:
        asyncio.run(run(os.path.join(directory, "processor.db")))


def test_due_outcome_job_records_each_available_horizon_once():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc)
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
            for horizon, price in ((15, 100.4), (30, 99.0), (60, 100.5)):
                session.add(Candle(
                    symbol="BTCUSDT",
                    interval="1m",
                    time=alert_time + timedelta(minutes=horizon),
                    open=100,
                    high=max(100, price),
                    low=min(100, price),
                    close=price,
                    volume=10,
                ))
            await session.commit()
            count = await evaluate_due_outcomes(session, now)
            await session.commit()
            assert count == 3
            results = list((await session.scalars(
                select(AlertOutcome).order_by(AlertOutcome.horizon_minutes)
            )).all())
            assert [row.horizon_minutes for row in results] == [15, 30, 60]
            assert [row.hit for row in results] == [True, False, True]
            assert await evaluate_due_outcomes(session, now) == 0
        await engine.dispose()

    asyncio.run(run())


def test_daily_calibration_logs_change_and_obeys_toggle():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        settings = get_settings()
        old_minimum = settings.calibration_min_samples
        settings.calibration_min_samples = 20
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
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
                    return_pct=1.0,
                    hit=False,
                ))
            await session.commit()
            changes = await calibrate_rules(session, now)
            await session.commit()
            assert len(changes) == 1
            assert changes[0].event_type == "pump"
            assert changes[0].new_threshold > changes[0].old_threshold
            assert changes[0].sample_count == 20
            assert "below" in changes[0].reason
            assert await session.get(RuleCalibration, "pump") is not None
            assert await calibrate_rules(session, now + timedelta(hours=1)) == []
            enabled = await session.get(RuntimeSetting, "calibration_enabled")
            enabled.value = False
            last = await session.get(RuntimeSetting, "last_calibration_at")
            last.value = (now - timedelta(days=2)).isoformat()
            await session.commit()
            assert await calibrate_rules(session, now + timedelta(days=1)) == []
        settings.calibration_min_samples = old_minimum
        await engine.dispose()

    asyncio.run(run())
