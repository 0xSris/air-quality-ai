from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_name: str
    environment: str


class SiteSummary(BaseModel):
    site_id: int
    latitude: float
    longitude: float
    train_rows: int
    unseen_rows: int
    train_start: datetime
    train_end: datetime


class DatasetSummaryResponse(BaseModel):
    total_sites: int
    total_train_rows: int
    total_unseen_rows: int
    features: list[str]
    targets: list[str]
    sites: list[SiteSummary]


class PollutantPoint(BaseModel):
    timestamp: datetime
    O3: float = Field(alias="o3")
    NO2: float = Field(alias="no2")
    source: str
    us_aqi: float | None = None
    european_aqi: float | None = None


class TrendResponse(BaseModel):
    site_id: int
    points: list[PollutantPoint]


class ForecastRequest(BaseModel):
    site_id: int
    horizon_hours: int | None = None
    model_name: str | None = None


class ForecastPoint(BaseModel):
    timestamp: datetime
    o3: float
    no2: float
    o3_lower: float
    o3_upper: float
    no2_lower: float
    no2_upper: float


class ForecastResponse(BaseModel):
    site_id: int
    horizon_hours: int
    model_name: str
    generated_at: datetime
    points: list[ForecastPoint]


class LiveResponse(BaseModel):
    site_id: int
    current: PollutantPoint
    recent: list[PollutantPoint]
    playback_position: int
    mode: str
    provider: str
    source_label: str
    fallback_used: bool
    last_updated: datetime


class LiveNetworkLocation(BaseModel):
    key: str
    name: str
    country: str
    region: str
    latitude: float
    longitude: float
    current: PollutantPoint
    recent: list[PollutantPoint] = []
    provider: str
    source_label: str
    fallback_used: bool
    last_updated: datetime


class LiveNetworkResponse(BaseModel):
    scope: Literal["india", "global"]
    generated_at: datetime
    locations: list[LiveNetworkLocation]


class AlertItem(BaseModel):
    site_id: int
    pollutant: Literal["O3", "NO2"]
    severity: Literal["info", "warning", "critical"]
    message: str
    timestamp: datetime
    value: float
    threshold: float


class AlertsResponse(BaseModel):
    site_id: int | None = None
    alerts: list[AlertItem]


class ModelMetadataResponse(BaseModel):
    active_model: str
    available_models: list[str]
    metrics: dict
    feature_columns: list[str]
    model_feature_columns: dict[str, list[str]] | None = None
    training_data_sources: list[str] | None = None
    external_feature_columns: list[str] | None = None
    targets: list[str]
