from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd


OPENMETEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
EXTERNAL_FEATURE_COLUMNS = [
    "external_ozone",
    "external_nitrogen_dioxide",
    "external_us_aqi",
    "external_european_aqi",
]


@dataclass(slots=True)
class OpenMeteoConfig:
    timezone: str = "Asia/Kolkata"
    domains: str = "cams_global"
    timeout_seconds: float = 30.0
    base_url: str = OPENMETEO_URL


class OpenMeteoAirQualityClient:
    def __init__(self, config: OpenMeteoConfig) -> None:
        self.config = config

    def fetch_range(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        site_id: int,
    ) -> pd.DataFrame:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "ozone,nitrogen_dioxide,us_aqi,european_aqi",
            "timezone": self.config.timezone,
            "domains": self.config.domains,
            "start_date": start_date,
            "end_date": end_date,
        }
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.get(self.config.base_url, params=params)
            response.raise_for_status()
        return self._hourly_frame(response.json(), site_id=site_id)

    def fetch_live_window(
        self,
        *,
        latitude: float,
        longitude: float,
        site_id: int,
        past_hours: int,
        forecast_hours: int,
    ) -> tuple[pd.DataFrame, dict]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "ozone,nitrogen_dioxide,us_aqi,european_aqi",
            "current": "ozone,nitrogen_dioxide,us_aqi,european_aqi",
            "timezone": self.config.timezone,
            "domains": self.config.domains,
            "past_hours": past_hours,
            "forecast_hours": forecast_hours,
        }
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.get(self.config.base_url, params=params)
            response.raise_for_status()
        payload = response.json()
        return self._hourly_frame(payload, site_id=site_id), payload.get("current", {})

    def _hourly_frame(self, payload: dict, *, site_id: int) -> pd.DataFrame:
        hourly = payload.get("hourly", {})
        if not hourly:
            return pd.DataFrame(columns=["site_id", "timestamp", *EXTERNAL_FEATURE_COLUMNS, "data_source"])
        frame = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(hourly.get("time", [])),
                "external_ozone": hourly.get("ozone", []),
                "external_nitrogen_dioxide": hourly.get("nitrogen_dioxide", []),
                "external_us_aqi": hourly.get("us_aqi", []),
                "external_european_aqi": hourly.get("european_aqi", []),
            }
        )
        if frame.empty:
            return pd.DataFrame(columns=["site_id", "timestamp", *EXTERNAL_FEATURE_COLUMNS, "data_source"])
        hourly_frame = (
            frame.set_index("timestamp")
            .sort_index()
            .resample("1h")
            .mean()
            .interpolate(method="time", limit_direction="both")
            .reset_index()
        )
        hourly_frame["site_id"] = site_id
        hourly_frame["data_source"] = "openmeteo"
        return hourly_frame

    @staticmethod
    def cache_frame(frame: pd.DataFrame, cache_path: Path) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(cache_path, index=False)

    @staticmethod
    def load_cached_frame(cache_path: Path) -> pd.DataFrame | None:
        if not cache_path.exists():
            return None
        return pd.read_parquet(cache_path)

    @staticmethod
    def current_from_payload(current: dict) -> dict:
        if not current:
            return {}
        timestamp = pd.to_datetime(current.get("time")).to_pydatetime() if current.get("time") else datetime.utcnow()
        return {
            "timestamp": timestamp,
            "o3": float(current.get("ozone", 0.0) or 0.0),
            "no2": float(current.get("nitrogen_dioxide", 0.0) or 0.0),
            "us_aqi": float(current.get("us_aqi", 0.0) or 0.0),
            "european_aqi": float(current.get("european_aqi", 0.0) or 0.0),
        }
