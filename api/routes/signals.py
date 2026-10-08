from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import CandleOut, SignalOut
from processing.aggregator import merge_candle_history, resample_candles
from storage.db import get_db_session
from storage.models import Candle, Signal
from storage.repository import get_latest_signals, list_candles

router = APIRouter(prefix="/signals", tags=["signals"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/latest", response_model=list[SignalOut])
async def latest_signals(session: SessionDep) -> list[Signal]:
    rows = await get_latest_signals(session)
    if not rows:
        raise HTTPException(status_code=503, detail="Market data has not been processed yet")
    return rows


@router.get("/candles", response_model=list[CandleOut])
async def get_candles(
    session: SessionDep,
    symbol: str,
    interval: str = "1m",
    limit: int = Query(default=120, ge=2, le=1000),
) -> list[Candle]:
    intervals = {"1m": 1, "5m": 5, "15m": 15}
    if interval not in intervals:
        raise HTTPException(status_code=422, detail="Supported intervals are 1m, 5m, and 15m")
    multiplier = intervals[interval]
    if multiplier == 1:
        rows = list(reversed(await list_candles(session, symbol.upper(), "1m", limit)))
        if not rows:
            raise HTTPException(status_code=404, detail="No candles available for this symbol and interval")
        return rows

    stored_rows = list(reversed(await list_candles(
        session, symbol.upper(), interval, limit,
    )))
    one_minute_rows = list(reversed(await list_candles(
        session, symbol.upper(), "1m", limit * multiplier,
    )))
    seeded = [
        {
            "time": row.time,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in stored_rows
    ]
    live = resample_candles([
        {
            "time": row.time,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in one_minute_rows
    ], multiplier)
    result = merge_candle_history(seeded, live, limit)
    if not result:
        raise HTTPException(status_code=404, detail="No candles available for this symbol and interval")
    return result