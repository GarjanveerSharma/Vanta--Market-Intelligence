from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./crypto_sentinel.db"
    redis_url: str = "memory://"
    binance_ws_url: str = "wss://stream.binance.com:9443/stream"
    binance_rest_url: str = "https://api.binance.com"
    coins_config: str = "config/coins.yaml"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, validation_alias=AliasChoices("PORT", "API_PORT"))
    log_level: str = "INFO"
    news_feed_url: str = ""
    admin_api_key: str = ""
    alert_confidence_threshold: float = 0.55
    alert_cooldown_seconds: int = 600
    outcome_move_threshold_pct: float = 0.3
    calibration_min_samples: int = 20
    calibration_low_hit_rate_pct: float = 45.0
    calibration_confidence_step: float = 0.05
    calibration_confidence_min: float = 0.55
    calibration_confidence_max: float = 0.95
    regime_adx_threshold: float = 25.0
    regime_high_volatility_atr_pct: float = 1.0
    high_volatility_confidence_multiplier: float = 0.75
    high_volatility_stop_multiplier: float = 1.5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()