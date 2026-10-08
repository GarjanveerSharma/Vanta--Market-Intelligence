import asyncio

import pytest

import ingestion.binance_ws as binance_ws
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


def test_history_loader_uses_public_fallback_to_seed_full_candle_history(monkeypatch):
    published = []
    requested = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                [1700000000000, "100", "102", "99", "101", "12.5"],
                [1700000060000, "101", "103", "100", "102", "13.5"],
            ]

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params):
            requested.append(url)
            if url.startswith("https://primary.example"):
                raise history_loader.httpx.ConnectError("primary unavailable")
            assert params == {"symbol": "BTCUSDT", "interval": "1m", "limit": 120}
            return Response()

    async def publish(event):
        published.append(event)

    settings = history_loader.get_settings()
    monkeypatch.setattr(settings, "binance_rest_url", "https://primary.example")
    monkeypatch.setattr(history_loader.httpx, "AsyncClient", lambda timeout: Client())
    monkeypatch.setattr(history_loader, "publish_candle", publish)

    asyncio.run(history_loader.load_recent_candles(["BTCUSDT"], "1m"))

    assert requested == [
        "https://primary.example/api/v3/klines",
        "https://data-api.binance.vision/api/v3/klines",
    ]
    assert len(published) == 2
    assert published[0]["historical"] is True
    assert published[0]["bootstrap_latest"] is False
    assert published[1]["historical"] is True
    assert published[1]["bootstrap_latest"] is True
    assert published[1]["close"] == 102.0


def test_latest_candle_loader_uses_public_fallback_and_publishes_live_candle(monkeypatch):
    published = []
    requested = []

    class Response:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return self.rows

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params):
            requested.append(url)
            if url.startswith("https://primary.example"):
                raise history_loader.httpx.ConnectError("primary unavailable")
            assert params == {"symbol": "BTCUSDT", "interval": "1m", "limit": 2}
            return Response([
                [1700000000000, "100", "101", "99", "100.5", "10"],
                [1700000060000, "100.5", "102", "100", "101.5", "12.5"],
            ])

    async def publish(event):
        published.append(event)

    settings = history_loader.get_settings()
    monkeypatch.setattr(settings, "binance_rest_url", "https://primary.example")
    monkeypatch.setattr(history_loader.httpx, "AsyncClient", lambda timeout: Client())
    monkeypatch.setattr(history_loader, "publish_candle", publish)

    count = asyncio.run(history_loader.load_latest_candles(["BTCUSDT"], "1m"))

    assert count == 1
    assert requested == [
        "https://primary.example/api/v3/klines",
        "https://data-api.binance.vision/api/v3/klines",
    ]
    assert published == [{
        "symbol": "BTCUSDT",
        "interval": "1m",
        "time": 1700000060000,
        "open": 100.5,
        "high": 102.0,
        "low": 100.0,
        "close": 101.5,
        "volume": 12.5,
    }]


def test_latest_candle_loader_rejects_unsupported_intervals():
    with pytest.raises(ValueError, match="interval"):
        asyncio.run(history_loader.load_latest_candles(["BTCUSDT"], "2m"))


def test_market_ingestion_polls_rest_after_websocket_failure(monkeypatch):
    fallback_calls = []

    class BrokenConnection:
        async def __aenter__(self):
            raise OSError("websocket blocked")

        async def __aexit__(self, *args):
            return None

    async def seed(*args):
        return None

    async def load_latest(symbols, interval):
        fallback_calls.append((symbols, interval))

    async def cancel_sleep(delay):
        raise asyncio.CancelledError

    monkeypatch.setattr(binance_ws, "load_symbols", lambda path: ["btcusdt"])
    monkeypatch.setattr(binance_ws, "seed_recent_candles", seed)
    monkeypatch.setattr(binance_ws, "load_latest_candles", load_latest)
    monkeypatch.setattr(binance_ws, "connect", lambda *args, **kwargs: BrokenConnection())
    monkeypatch.setattr(binance_ws.asyncio, "sleep", cancel_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(binance_ws.consume_market_data())

    assert fallback_calls == [(["btcusdt"], "1m")]
