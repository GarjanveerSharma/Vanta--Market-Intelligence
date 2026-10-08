from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.realtime import realtime_hub

router = APIRouter()


@router.websocket("/ws")
async def market_updates(websocket: WebSocket) -> None:
    await realtime_hub.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        realtime_hub.disconnect(websocket)
