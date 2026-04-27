from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="Air Quality AI", alias="APP_NAME")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")
    app_db_path: Path = Field(default=Path("./backend/app.db"), alias="APP_DB_PATH")
    data_root: Path = Field(default=Path("./ml/data"), alias="DATA_ROOT")
    raw_data_dir: Path = Field(default=Path("./ml/data/raw/Data_SIH_2025"), alias="RAW_DATA_DIR")
    processed_data_dir: Path = Field(default=Path("./ml/data/processed"), alias="PROCESSED_DATA_DIR")
    artifacts_dir: Path = Field(default=Path("./ml/artifacts"), alias="ARTIFACTS_DIR")
    external_data_dir: Path = Field(default=Path("./ml/data/external"), alias="EXTERNAL_DATA_DIR")
    live_source_mode: str = Field(default="auto", alias="LIVE_SOURCE_MODE")
    live_external_provider: str = Field(default="openmeteo", alias="LIVE_EXTERNAL_PROVIDER")
    live_external_timezone: str = Field(default="Asia/Kolkata", alias="LIVE_EXTERNAL_TIMEZONE")
    live_external_domains: str = Field(default="cams_global", alias="LIVE_EXTERNAL_DOMAINS")
    live_external_past_hours: int = Field(default=24, alias="LIVE_EXTERNAL_PAST_HOURS")
    live_external_forecast_hours: int = Field(default=24, alias="LIVE_EXTERNAL_FORECAST_HOURS")
    live_external_timeout_seconds: float = Field(default=30.0, alias="LIVE_EXTERNAL_TIMEOUT_SECONDS")
    live_refresh_seconds: int = Field(default=10, alias="LIVE_REFRESH_SECONDS")
    forecast_horizon_hours: int = Field(default=24, alias="FORECAST_HORIZON_HOURS")
    lookback_hours: int = Field(default=168, alias="LOOKBACK_HOURS")
    alert_o3_threshold: float = Field(default=100.0, alias="ALERT_O3_THRESHOLD")
    alert_no2_threshold: float = Field(default=80.0, alias="ALERT_NO2_THRESHOLD")
    simulation_speed: int = Field(default=120, alias="SIMULATION_SPEED")
    default_site_id: int = Field(default=1, alias="DEFAULT_SITE_ID")
    model_name: str = Field(default="baseline_random_forest", alias="MODEL_NAME")
    model_device: str = Field(default="cpu", alias="MODEL_DEVICE")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    research_export_dir: Path = Field(default=Path("./backend/exports"), alias="RESEARCH_EXPORT_DIR")
    enable_external_training_augmentation: bool = Field(
        default=False, alias="ENABLE_EXTERNAL_TRAINING_AUGMENTATION"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    settings.external_data_dir.mkdir(parents=True, exist_ok=True)
    settings.research_export_dir.mkdir(parents=True, exist_ok=True)
    settings.app_db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
