from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
import asyncio

from fastapi.testclient import TestClient

from config.settings import get_settings
from storage.db import close_database, get_engine, get_session_factory
from storage.models import Alert, AlertOutcome, Candle, Signal


def test_api_routes_contract_and_cors(monkeypatch):
    from api.main import app

    with tempfile.TemporaryDirectory() as directory:
        monkeypatch.setenv("APP_ENV", "test")
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{os.path.join(directory, 'api.db')}")
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")
        monkeypatch.setenv("PORT", "8123")
        monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()

        try:
            assert get_settings().api_port == 8123
            with TestClient(app) as client:
                now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
                async def seed_api_data():
                    async with get_session_factory()() as session:
                        session.add_all([
                            Candle(
                                symbol="BTCUSDT",
                                interval="1m",
                                time=now - timedelta(minutes=24 - index),
                                open=100 + index * 0.1,
                                high=100.2 + index * 0.1,
                                low=99.8 + index * 0.1,
                                close=100.1 + index * 0.1,
                                volume=10,
                            )
                            for index in range(25)
                        ])
                        session.add(Signal(
                            symbol="BTCUSDT",
                            time=now,
                            price=102.4,
                            change_1h=1.2,
                            rsi=55,
                            volume_z=1.1,
                            signal="BUY",
                            confidence=0.8,
                            regime="TRENDING_UP",
                            timeframe_agreement={"1m": True, "5m": True, "15m": False},
                            track_record={"sample_count": 10, "enough_data": True},
                            filter_version="mtf-v1",
                            signal_quality="partial",
                        ))
                        alert = Alert(
                            time=now,
                            symbol="BTCUSDT",
                            event_type="breakout",
                            action="BUY",
                            confidence=0.8,
                            price=102.4,
                            stop_loss=99.3,
                            explanation="Resistance breakout",
                            regime="TRENDING_UP",
                            timeframe_agreement={"1m": True, "5m": True, "15m": False},
                            track_record={"sample_count": 10, "hit_rate_pct": 60, "enough_data": True},
                            filter_version="mtf-v1",
                        )
                        session.add(alert)
                        await session.flush()
                        session.add(AlertOutcome(
                            alert_id=alert.id,
                            horizon_minutes=60,
                            checked_at=now,
                            return_pct=0.5,
                            hit=True,
                        ))
                        await session.commit()

                asyncio.run(seed_api_data())
                health = client.get("/health")
                assert health.status_code == 200
                assert health.json() == {"status": "ok"}
                metrics = client.get("/metrics")
                assert metrics.status_code == 200
                assert "sentinel_http_requests_total" in metrics.text
                alerts = client.get("/alerts").json()
                assert alerts[0]["regime"] == "TRENDING_UP"
                assert alerts[0]["timeframe_agreement"]["15m"] is False
                assert "track_record" in alerts[0]
                assert "filter_version" in alerts[0]
                records = client.get("/track-record").json()
                assert records[0]["sample_count"] == 1
                assert records[0]["enough_data"] is False
                assert client.get("/calibration/log").json() == []
                assert client.get("/track-record/changes").json() == []
                assert client.get("/track-record/settings").status_code == 200
                assert client.post(
                    "/track-record/settings",
                    json={"enabled": False},
                ).status_code == 403
                assert client.post(
                    "/track-record/settings",
                    headers={"X-Admin-Key": "wrong-key"},
                    json={"enabled": False},
                ).status_code == 403
                admin_update = client.post(
                    "/track-record/settings",
                    headers={"X-Admin-Key": "test-admin-key"},
                    json={"enabled": False},
                )
                assert admin_update.status_code == 200
                assert admin_update.json()["enabled"] is False
                signals = client.get("/signals/latest").json()
                assert signals[0]["timeframe_agreement"]["15m"] is False
                assert signals[0]["filter_version"] == "mtf-v1"
                assert "track_record" in signals[0]
                assert len(client.get("/signals/candles?symbol=BTCUSDT").json()) == 25
                backtest = client.get("/backtest/results?symbol=BTCUSDT")
                assert backtest.status_code == 200
                assert {"total_alerts", "equity", "by_event"} <= backtest.json().keys()
                assert alerts[0]["outcome"] == "correct"
                with client.websocket_connect("/ws") as websocket:
                    websocket.send_text("ping")
                    assert websocket.receive_json() == {"type": "pong"}
                preflight = client.options(
                    "/health",
                    headers={
                        "Origin": "http://localhost:5173",
                        "Access-Control-Request-Method": "GET",
                    },
                )
                assert preflight.status_code == 200
                assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
                vercel_preflight = client.options(
                    "/health",
                    headers={
                        "Origin": "https://vanta-git-main-example.vercel.app",
                        "Access-Control-Request-Method": "GET",
                    },
                )
                assert vercel_preflight.status_code == 200
                assert vercel_preflight.headers["access-control-allow-origin"] == (
                    "https://vanta-git-main-example.vercel.app"
                )
        finally:
            asyncio.run(close_database())
            get_settings.cache_clear()
