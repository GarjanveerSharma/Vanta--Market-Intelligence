from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (UniqueConstraint("symbol", "interval", "time", name="uq_candle_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    interval: Mapped[str] = mapped_column(String(10), default="1m")
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    price: Mapped[float] = mapped_column(Float)
    change_1h: Mapped[float] = mapped_column(Float)
    rsi: Mapped[float] = mapped_column(Float)
    volume_z: Mapped[float] = mapped_column(Float)
    signal: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float] = mapped_column(Float)
    regime: Mapped[str] = mapped_column(String(32), default="SIDEWAYS")
    timeframe_agreement: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict)
    track_record: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    filter_version: Mapped[str] = mapped_column(String(32), default="mtf-v1")
    signal_quality: Mapped[str] = mapped_column(String(20), default="unconfirmed")
    adx: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    action: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    regime: Mapped[str] = mapped_column(String(32), default="SIDEWAYS")
    timeframe_agreement: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict)
    track_record: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    filter_version: Mapped[str] = mapped_column(String(32), default="legacy-v0")


class AlertOutcome(Base):
    __tablename__ = "alert_outcomes"
    __table_args__ = (UniqueConstraint("alert_id", "horizon_minutes", name="uq_alert_outcome_horizon"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    horizon_minutes: Mapped[int] = mapped_column(Integer)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class RuntimeSetting(Base):
    __tablename__ = "runtime_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)


class RuleCalibration(Base):
    __tablename__ = "rule_calibrations"

    event_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    min_confidence: Mapped[float] = mapped_column(Float)


class CalibrationLog(Base):
    __tablename__ = "calibration_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    old_threshold: Mapped[float] = mapped_column(Float)
    new_threshold: Mapped[float] = mapped_column(Float)
    hit_rate_pct: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)


CalibrationChange = CalibrationLog


class NewsItem(Base):
    __tablename__ = "news_items"
    __table_args__ = (UniqueConstraint("url", name="uq_news_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2000), unique=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)