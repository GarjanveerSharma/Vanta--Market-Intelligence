from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import Alert, AlertOutcome, Candle, Signal


async def get_candle(
    session: AsyncSession,
    symbol: str,
    interval: str,
    time: datetime,
) -> Candle | None:
    return await session.scalar(select(Candle).where(
        Candle.symbol == symbol,
        Candle.interval == interval,
        Candle.time == time,
    ))


async def list_candles(
    session: AsyncSession,
    symbol: str,
    interval: str,
    limit: int,
    since: datetime | None = None,
) -> list[Candle]:
    query = select(Candle).where(
        Candle.symbol == symbol,
        Candle.interval == interval,
    )
    if since is not None:
        query = query.where(Candle.time >= since)
    return list((await session.scalars(
        query.order_by(Candle.time.desc()).limit(limit)
    )).all())


async def upsert_candle(
    session: AsyncSession,
    symbol: str,
    interval: str,
    time: datetime,
    values: dict[str, float],
) -> Candle:
    candle = await get_candle(session, symbol, interval, time)
    if candle is None:
        candle = Candle(symbol=symbol, interval=interval, time=time, **values)
        session.add(candle)
    else:
        for name, value in values.items():
            setattr(candle, name, value)
    return candle


async def get_latest_signals(session: AsyncSession) -> list[Signal]:
    newest = select(
        Signal.symbol,
        func.max(Signal.time).label("max_time"),
    ).group_by(Signal.symbol).subquery()
    query = select(Signal).join(
        newest,
        (Signal.symbol == newest.c.symbol) & (Signal.time == newest.c.max_time),
    ).order_by(Signal.symbol)
    return list((await session.scalars(query)).all())


async def save_signal(
    session: AsyncSession,
    symbol: str,
    time: datetime,
    values: dict[str, Any],
) -> Signal:
    signal = await session.scalar(select(Signal).where(
        Signal.symbol == symbol,
        Signal.time == time,
    ))
    if signal is None:
        signal = Signal(symbol=symbol, time=time, **values)
        session.add(signal)
    else:
        for name, value in values.items():
            setattr(signal, name, value)
    return signal


async def list_alerts(
    session: AsyncSession,
    symbol: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
) -> list[Alert]:
    query = select(Alert).order_by(Alert.time.desc()).limit(limit)
    if symbol:
        query = query.where(Alert.symbol == symbol.upper())
    if event_type:
        query = query.where(Alert.event_type == event_type)
    return list((await session.scalars(query)).all())


def save_alert(session: AsyncSession, alert: Alert) -> None:
    session.add(alert)


def add_alert_outcome(session: AsyncSession, outcome: AlertOutcome) -> None:
    session.add(outcome)


async def delete_expired_market_data(
    session: AsyncSession,
    candle_cutoff: datetime,
    alert_cutoff: datetime,
) -> dict[str, int]:
    candle_result = await session.execute(delete(Candle).where(
        Candle.interval == "1m",
        Candle.time < candle_cutoff,
    ))
    expired_alert_ids = select(Alert.id).where(Alert.time < alert_cutoff)
    outcomes_result = await session.execute(delete(AlertOutcome).where(
        AlertOutcome.alert_id.in_(expired_alert_ids)
    ))
    alerts_result = await session.execute(delete(Alert).where(Alert.time < alert_cutoff))
    return {
        "candles": int(candle_result.rowcount or 0),
        "outcomes": int(outcomes_result.rowcount or 0),
        "alerts": int(alerts_result.rowcount or 0),
    }
