import asyncio
import time

import pytest

from api.realtime import RealtimeHub


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append((time.monotonic(), message))


@pytest.mark.asyncio
async def test_realtime_hub_throttles_per_symbol_and_keeps_latest_market_values():
    hub = RealtimeHub(max_updates_per_second=2)
    client = FakeWebSocket()
    hub._clients.add(client)

    await hub.publish({
        "type": "market_update",
        "symbol": "BTCUSDT",
        "price": 100,
        "alerts": [{"id": 1}],
    })
    await hub.publish({
        "type": "market_update",
        "symbol": "BTCUSDT",
        "price": 101,
        "alerts": [{"id": 2}],
    })
    await hub.publish({
        "type": "market_update",
        "symbol": "ETHUSDT",
        "price": 50,
        "alerts": [],
    })

    await asyncio.sleep(0.55)

    btc_updates = [message for _, message in client.messages if message["symbol"] == "BTCUSDT"]
    assert [message["price"] for message in btc_updates] == [100, 101]
    assert btc_updates[1]["alerts"] == [{"id": 2}]
    assert client.messages[2][0] != client.messages[1][0]
