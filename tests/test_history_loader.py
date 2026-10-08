import asyncio

import pytest

import ingestion.history_loader as history_loader


def test_history_loader_publishes_binance_candles(monkeypatch):
    published = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [[1700000000000, "100", "102", "99", "101", "12.5"]]

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params):
            assert url.endswith("/api/v3/klines")
            assert params == {"symbol": "BTCUSDT", "interval": "1m", "limit": 120}
            return Response()

    async def publish(event):
        published.append(event)

    monkeypatch.setattr(history_loader.httpx, "AsyncClient", lambda timeout: Client())
    monkeypatch.setattr(history_loader, "publish_candle", publish)

    asyncio.run(history_loader.load_recent_candles(["BTCUSDT"], "1m"))

    assert published == [{
        "symbol": "BTCUSDT",
        "interval": "1m",
        "time": 1700000000000,
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 12.5,
        "historical": True,
        "bootstrap_latest": True,
    }]
def test_history_loader_rejects_unsupported_intervals():
    with pytest.raises(ValueError, match="interval"):
        asyncio.run(history_loader.load_recent_candles(["BTCUSDT"], "2m"))
