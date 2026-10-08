from __future__ import annotations

import secrets

from fastapi import APIRouter
from fastapi import Header, HTTPException
from sqlalchemy import select

from alerts.track_record import CALIBRATION_ENABLED_KEY
from api.deps import SessionDep
from api.schemas import (
    CalibrationChangeOut,
    CalibrationSettingsIn,
    CalibrationSettingsOut,
    TrackRecordGroup,
)
from config.settings import get_settings
from storage.models import CalibrationChange, RuntimeSetting
from evaluation.stats import get_track_record_stats

router = APIRouter(tags=["track record"])


@router.get("/track-record", response_model=list[TrackRecordGroup])
async def track_record(session: SessionDep) -> list[dict[str, object]]:
    return await get_track_record_stats(session)


@router.get("/calibration/log", response_model=list[CalibrationChangeOut])
@router.get("/track-record/changes", response_model=list[CalibrationChangeOut])
async def calibration_changes(
    session: SessionDep,
    limit: int = 100,
) -> list[CalibrationChange]:
    limit = max(1, min(limit, 500))
    return list((await session.scalars(
        select(CalibrationChange).order_by(CalibrationChange.changed_at.desc()).limit(limit)
    )).all())


@router.get("/track-record/settings", response_model=CalibrationSettingsOut)
async def calibration_settings(session: SessionDep) -> dict[str, object]:
    settings = get_settings()
    enabled = await session.get(RuntimeSetting, CALIBRATION_ENABLED_KEY)
    return {
        "enabled": bool(enabled.value) if enabled is not None else True,
        "outcome_move_threshold_pct": settings.outcome_move_threshold_pct,
        "alert_confidence_threshold": settings.alert_confidence_threshold,
        "regime_adx_threshold": settings.regime_adx_threshold,
        "regime_high_volatility_atr_pct": settings.regime_high_volatility_atr_pct,
        "high_volatility_confidence_multiplier": settings.high_volatility_confidence_multiplier,
        "high_volatility_stop_multiplier": settings.high_volatility_stop_multiplier,
        "min_samples": settings.calibration_min_samples,
        "low_hit_rate_pct": settings.calibration_low_hit_rate_pct,
        "confidence_step": settings.calibration_confidence_step,
        "confidence_min": settings.calibration_confidence_min,
        "confidence_max": settings.calibration_confidence_max,
    }


@router.post("/track-record/settings", response_model=CalibrationSettingsOut)
async def update_calibration_settings(
    data: CalibrationSettingsIn,
    session: SessionDep,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> dict[str, object]:
    admin_key = get_settings().admin_api_key
    if not admin_key or not x_admin_key or not secrets.compare_digest(x_admin_key, admin_key):
        raise HTTPException(status_code=403, detail="Valid X-Admin-Key required")
    setting = await session.get(RuntimeSetting, CALIBRATION_ENABLED_KEY)
    if setting is None:
        session.add(RuntimeSetting(key=CALIBRATION_ENABLED_KEY, value=data.enabled))
    else:
        setting.value = data.enabled
    await session.commit()
    return await calibration_settings(session)
