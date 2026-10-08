from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CandleOut(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class SignalOut(BaseModel):
    symbol: str
    price: float
    change_1h: float
    rsi: float
    volume_z: float
    signal: Literal["BUY", "SELL", "HOLD", "AVOID"]
    confidence: float = Field(ge=0, le=1)
    regime: str = "SIDEWAYS"
    timeframe_agreement: dict[str, bool] = Field(default_factory=dict)
    track_record: dict[str, object] = Field(default_factory=dict)
    filter_version: str = "mtf-v1"
    signal_quality: str = "unconfirmed"
    adx: float | None = None
    atr_pct: float | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    time: datetime
    symbol: str
    event_type: str
    action: Literal["BUY", "SELL", "HOLD", "AVOID"]
    confidence: float
    price: float
    stop_loss: float
    explanation: str
    regime: str = "SIDEWAYS"
    filter_version: str = "legacy-v0"
    timeframe_agreement: dict[str, bool] = Field(default_factory=dict)
    track_record: dict[str, object] = Field(default_factory=dict)
    hit_rate_pct: float | None = None
    sample_count: int = 0
    outcome: Literal["correct", "wrong", "pending"] = "pending"


class TrackRecordGroup(BaseModel):
    symbol: str
    event_type: str
    hit_rate_pct: float | None
    sample_count: int
    correct_count: int
    regime: str | None = None
    filter_version: str = "legacy-v0"
    enough_data: bool


class CalibrationChangeOut(BaseModel):
    changed_at: datetime
    event_type: str
    old_threshold: float
    new_threshold: float
    hit_rate_pct: float
    sample_count: int
    reason: str


class CalibrationSettingsOut(BaseModel):
    enabled: bool
    outcome_move_threshold_pct: float
    alert_confidence_threshold: float
    regime_adx_threshold: float
    regime_high_volatility_atr_pct: float
    high_volatility_confidence_multiplier: float
    high_volatility_stop_multiplier: float
    min_samples: int
    low_hit_rate_pct: float
    confidence_step: float
    confidence_min: float
    confidence_max: float


class CalibrationSettingsIn(BaseModel):
    enabled: bool


class NewsIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    published_at: datetime | None = None
    summary: str = Field(default="", max_length=10_000)