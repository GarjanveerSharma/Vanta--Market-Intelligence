from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class RealtimeHub:
    def __init__(self, max_updates_per_second: int = 2) -> None:
        if max_updates_per_second < 1:
            raise ValueError("max_updates_per_second must be positive")
        self._interval = 1 / max_updates_per_second
        self._clients: set[WebSocket] = set()
        self._last_sent: dict[str, float] = {}
        self._pending: dict[str, dict[str, Any]] = {}
        self._scheduled: dict[str, asyncio.Task[None]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def publish(self, message: dict[str, Any]) -> None:
        symbol = str(message["symbol"])
        now = time.monotonic()
        remaining = self._interval - (now - self._last_sent.get(symbol, 0))
        if remaining > 0:
            pending = self._pending.setdefault(symbol, {
                "type": "market_update",
                "symbol": symbol,
                "alerts": [],
                "outcomes": [],
            })
            if message.get("type") == "market_update":
                pending.update({
                    key: value for key, value in message.items()
                    if key not in {"alerts", "outcomes"}
                })
                pending["alerts"] = pending.get("alerts", []) + message.get("alerts", [])
                pending["outcomes"] = pending.get("outcomes", []) + message.get("outcomes", [])
            elif message.get("type") == "alert_outcome":
                pending["outcomes"] = pending.get("outcomes", []) + message.get("outcomes", [])
            if symbol not in self._scheduled:
                task = asyncio.create_task(self._publish_pending(symbol, remaining))
                self._scheduled[symbol] = task
            return
        await self._send(message)
        self._last_sent[symbol] = time.monotonic()

    async def _publish_pending(self, symbol: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            message = self._pending.pop(symbol, None)
            if message is not None:
                await self._send(message)
                self._last_sent[symbol] = time.monotonic()
        finally:
            self._scheduled.pop(symbol, None)

    async def _send(self, message: dict[str, Any]) -> None:
        failed: list[WebSocket] = []
        for client in tuple(self._clients):
            try:
                await client.send_json(message)
            except (WebSocketDisconnect, RuntimeError, OSError):
                failed.append(client)
            except Exception:
                logger.exception("Failed to send a market update to a WebSocket client")
                failed.append(client)
        for client in failed:
            self.disconnect(client)


realtime_hub = RealtimeHub()
