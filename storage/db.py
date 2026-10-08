from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import get_settings
from storage.models import Base


@lru_cache
def get_engine():
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def initialize_database() -> None:
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_migrate_existing_columns)


def _migrate_existing_columns(connection) -> None:
    inspector = inspect(connection)
    additions = {
        "signals": {
            "regime": "VARCHAR(32) NOT NULL DEFAULT 'SIDEWAYS'",
            "timeframe_agreement": "JSON NOT NULL DEFAULT '{}'",
            "signal_quality": "VARCHAR(20) NOT NULL DEFAULT 'unconfirmed'",
            "track_record": "JSON NOT NULL DEFAULT '{}'",
            "filter_version": "VARCHAR(32) NOT NULL DEFAULT 'mtf-v1'",
            "adx": "FLOAT",
            "atr_pct": "FLOAT",
        },
        "alerts": {
            "regime": "VARCHAR(32) NOT NULL DEFAULT 'SIDEWAYS'",
            "timeframe_agreement": "JSON NOT NULL DEFAULT '{}'",
            "track_record": "JSON NOT NULL DEFAULT '{}'",
            "filter_version": "VARCHAR(32) NOT NULL DEFAULT 'legacy-v0'",
        },
    }
    for table, columns in additions.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, definition in columns.items():
            if name not in existing:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                )
    if "calibration_changes" in inspector.get_table_names():
        connection.exec_driver_sql(
            "INSERT INTO calibration_log "
            "(id, changed_at, event_type, old_threshold, new_threshold, hit_rate_pct, sample_count, reason) "
            "SELECT old.id, old.changed_at, old.event_type, old.old_threshold, old.new_threshold, "
            "old.hit_rate_pct, old.sample_count, old.reason FROM calibration_changes old "
            "WHERE NOT EXISTS (SELECT 1 FROM calibration_log new WHERE new.id = old.id)"
        )


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


async def close_database() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()
        get_session_factory.cache_clear()