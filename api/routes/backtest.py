from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from api.deps import SessionDep
from backtest.replay import replay_candles
from storage.repository import list_candles

router = APIRouter(tags=["backtest"])


@router.get("/backtest/results")
async def backtest_results(
    session: SessionDep,
    symbol: str,
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, object]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = list(reversed(await list_candles(
        session,
        symbol.upper(),
        "1m",
        130_000,
        since,
    )))
    if len(rows) < 20:
        raise HTTPException(status_code=503, detail="Not enough stored candles to run a backtest")
    return replay_candles([
        {
            "time": row.time,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in rows
    ])
