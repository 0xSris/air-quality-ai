from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from backend.app.core.config import Settings
from backend.app.schemas.api import LiveNetworkLocation, LiveNetworkResponse, LiveResponse, PollutantPoint
from backend.app.services.repository import DataRepository
from ml.data.external_sources import OpenMeteoAirQualityClient, OpenMeteoConfig


@dataclass(frozen=True, slots=True)
class LiveNetworkSite:
    key: str
    name: str
    country: str
    region: str
    latitude: float
    longitude: float


INDIA_LIVE_NETWORK: tuple[LiveNetworkSite, ...] = (
    LiveNetworkSite("delhi", "Delhi", "India", "North", 28.6139, 77.2090),
    LiveNetworkSite("mumbai", "Mumbai", "India", "West", 19.0760, 72.8777),
    LiveNetworkSite("bengaluru", "Bengaluru", "India", "South", 12.9716, 77.5946),
    LiveNetworkSite("chennai", "Chennai", "India", "South", 13.0827, 80.2707),
    LiveNetworkSite("kolkata", "Kolkata", "India", "East", 22.5726, 88.3639),
    LiveNetworkSite("hyderabad", "Hyderabad", "India", "South", 17.3850, 78.4867),
    LiveNetworkSite("pune", "Pune", "India", "West", 18.5204, 73.8567),
    LiveNetworkSite("ahmedabad", "Ahmedabad", "India", "West", 23.0225, 72.5714),
    LiveNetworkSite("jaipur", "Jaipur", "India", "North", 26.9124, 75.7873),
    LiveNetworkSite("lucknow", "Lucknow", "India", "North", 26.8467, 80.9462),
)

GLOBAL_LIVE_NETWORK: tuple[LiveNetworkSite, ...] = (
    LiveNetworkSite("london", "London", "United Kingdom", "Europe", 51.5072, -0.1276),
    LiveNetworkSite("new_york", "New York", "United States", "North America", 40.7128, -74.0060),
    LiveNetworkSite("los_angeles", "Los Angeles", "United States", "North America", 34.0522, -118.2437),
    LiveNetworkSite("paris", "Paris", "France", "Europe", 48.8566, 2.3522),
    LiveNetworkSite("singapore", "Singapore", "Singapore", "Asia", 1.3521, 103.8198),
    LiveNetworkSite("tokyo", "Tokyo", "Japan", "Asia", 35.6762, 139.6503),
    LiveNetworkSite("beijing", "Beijing", "China", "Asia", 39.9042, 116.4074),
    LiveNetworkSite("sydney", "Sydney", "Australia", "Oceania", -33.8688, 151.2093),
)

_SITE_SNAPSHOT_CACHE: dict[int, tuple[datetime, LiveResponse]] = {}
_NETWORK_SNAPSHOT_CACHE: dict[str, tuple[datetime, LiveNetworkResponse]] = {}
_CACHE_TTL_SECONDS = 45


class SimulationProvider:
    def __init__(self, repository: DataRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def get_snapshot(self, site_id: int) -> LiveResponse:
        frame = self.repository.site_frame(site_id, split="unseen")
        position = int(datetime.utcnow().timestamp() // max(self.settings.live_refresh_seconds, 1)) % len(frame)
        recent = frame.iloc[max(0, position - 24) : position + 1]
        current_row = frame.iloc[position]
        current = PollutantPoint(
            timestamp=current_row.timestamp.to_pydatetime(),
            o3=float(current_row.O3_forecast),
            no2=float(current_row.NO2_forecast),
            source="live_simulated",
        )
        recent_points = [
            PollutantPoint(
                timestamp=row.timestamp.to_pydatetime(),
                o3=float(row.O3_forecast),
                no2=float(row.NO2_forecast),
                source="live_simulated",
            )
            for row in recent.itertuples()
        ]
        return LiveResponse(
            site_id=site_id,
            current=current,
            recent=recent_points,
            playback_position=position,
            mode=self.settings.live_source_mode,
            provider="simulation",
            source_label="Replay simulator from unseen SIH inputs",
            fallback_used=False,
            last_updated=datetime.utcnow(),
        )


class OpenMeteoLiveProvider:
    def __init__(self, repository: DataRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.client = OpenMeteoAirQualityClient(
            OpenMeteoConfig(
                timezone=settings.live_external_timezone,
                domains=settings.live_external_domains,
                timeout_seconds=settings.live_external_timeout_seconds,
            )
        )

    def get_snapshot(self, site_id: int) -> LiveResponse:
        site = self.repository.site_summary(site_id)
        frame, current_payload = self.client.fetch_live_window(
            latitude=site["latitude"],
            longitude=site["longitude"],
            site_id=site_id,
            past_hours=self.settings.live_external_past_hours,
            forecast_hours=self.settings.live_external_forecast_hours,
        )
        cache_path = self.settings.external_data_dir / "live_cache" / f"site_{site_id}_latest.parquet"
        self.client.cache_frame(frame, cache_path)
        current_data = self.client.current_from_payload(current_payload)
        current = PollutantPoint(
            timestamp=current_data["timestamp"],
            o3=current_data["o3"],
            no2=current_data["no2"],
            us_aqi=current_data["us_aqi"],
            european_aqi=current_data["european_aqi"],
            source="live_external",
        )
        recent = frame.tail(self.settings.live_external_past_hours)
        recent_points = [
            PollutantPoint(
                timestamp=row.timestamp.to_pydatetime(),
                o3=float(row.external_ozone),
                no2=float(row.external_nitrogen_dioxide),
                us_aqi=float(row.external_us_aqi) if pd.notna(row.external_us_aqi) else None,
                european_aqi=float(row.external_european_aqi) if pd.notna(row.external_european_aqi) else None,
                source="live_external",
            )
            for row in recent.itertuples()
        ]
        return LiveResponse(
            site_id=site_id,
            current=current,
            recent=recent_points,
            playback_position=max(len(recent_points) - 1, 0),
            mode=self.settings.live_source_mode,
            provider="openmeteo",
            source_label="Open-Meteo real-time air-quality feed",
            fallback_used=False,
            last_updated=datetime.utcnow(),
        )

    def get_network_snapshot(self, location: LiveNetworkSite) -> LiveNetworkLocation:
        frame, current_payload = self.client.fetch_live_window(
            latitude=location.latitude,
            longitude=location.longitude,
            site_id=0,
            past_hours=self.settings.live_external_past_hours,
            forecast_hours=self.settings.live_external_forecast_hours,
        )
        cache_path = self.settings.external_data_dir / "live_cache" / f"{location.key}_latest.parquet"
        self.client.cache_frame(frame, cache_path)
        current_data = self.client.current_from_payload(current_payload)
        current = PollutantPoint(
            timestamp=current_data["timestamp"],
            o3=current_data["o3"],
            no2=current_data["no2"],
            us_aqi=current_data["us_aqi"],
            european_aqi=current_data["european_aqi"],
            source="live_external",
        )
        recent = frame.tail(self.settings.live_external_past_hours)
        recent_points = [
            PollutantPoint(
                timestamp=row.timestamp.to_pydatetime(),
                o3=float(row.external_ozone),
                no2=float(row.external_nitrogen_dioxide),
                us_aqi=float(row.external_us_aqi) if pd.notna(row.external_us_aqi) else None,
                european_aqi=float(row.external_european_aqi) if pd.notna(row.external_european_aqi) else None,
                source="live_external",
            )
            for row in recent.itertuples()
        ]
        return LiveNetworkLocation(
            key=location.key,
            name=location.name,
            country=location.country,
            region=location.region,
            latitude=location.latitude,
            longitude=location.longitude,
            current=current,
            recent=recent_points,
            provider="openmeteo",
            source_label="Open-Meteo real-time air-quality feed",
            fallback_used=False,
            last_updated=datetime.utcnow(),
        )

    def cached_snapshot(self, site_id: int) -> LiveResponse | None:
        cache_path = self.settings.external_data_dir / "live_cache" / f"site_{site_id}_latest.parquet"
        if not cache_path.exists():
            return None
        frame = pd.read_parquet(cache_path)
        if frame.empty:
            return None
        recent = frame.tail(self.settings.live_external_past_hours)
        recent_points = [
            PollutantPoint(
                timestamp=pd.to_datetime(row.timestamp).to_pydatetime(),
                o3=float(row.external_ozone),
                no2=float(row.external_nitrogen_dioxide),
                us_aqi=float(row.external_us_aqi) if pd.notna(row.external_us_aqi) else None,
                european_aqi=float(row.external_european_aqi) if pd.notna(row.external_european_aqi) else None,
                source="live_external_cached",
            )
            for row in recent.itertuples()
        ]
        return LiveResponse(
            site_id=site_id,
            current=recent_points[-1],
            recent=recent_points,
            playback_position=max(len(recent_points) - 1, 0),
            mode=self.settings.live_source_mode,
            provider="openmeteo_cache",
            source_label="Cached Open-Meteo air-quality feed",
            fallback_used=True,
            last_updated=datetime.utcnow(),
        )

    def cached_network_snapshot(self, location: LiveNetworkSite) -> LiveNetworkLocation | None:
        cache_path = self.settings.external_data_dir / "live_cache" / f"{location.key}_latest.parquet"
        if not cache_path.exists():
            return None
        frame = pd.read_parquet(cache_path)
        if frame.empty:
            return None
        latest_row = frame.sort_values("timestamp").iloc[-1]
        current = PollutantPoint(
            timestamp=pd.to_datetime(latest_row.timestamp).to_pydatetime(),
            o3=float(latest_row.external_ozone),
            no2=float(latest_row.external_nitrogen_dioxide),
            us_aqi=float(latest_row.external_us_aqi) if pd.notna(latest_row.external_us_aqi) else None,
            european_aqi=float(latest_row.external_european_aqi) if pd.notna(latest_row.external_european_aqi) else None,
            source="live_external_cached",
        )
        recent = frame.sort_values("timestamp").tail(self.settings.live_external_past_hours)
        recent_points = [
            PollutantPoint(
                timestamp=pd.to_datetime(row.timestamp).to_pydatetime(),
                o3=float(row.external_ozone),
                no2=float(row.external_nitrogen_dioxide),
                us_aqi=float(row.external_us_aqi) if pd.notna(row.external_us_aqi) else None,
                european_aqi=float(row.external_european_aqi) if pd.notna(row.external_european_aqi) else None,
                source="live_external_cached",
            )
            for row in recent.itertuples()
        ]
        return LiveNetworkLocation(
            key=location.key,
            name=location.name,
            country=location.country,
            region=location.region,
            latitude=location.latitude,
            longitude=location.longitude,
            current=current,
            recent=recent_points,
            provider="openmeteo_cache",
            source_label="Cached Open-Meteo air-quality feed",
            fallback_used=True,
            last_updated=datetime.utcnow(),
        )


class LiveDataService:
    def __init__(self, repository: DataRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.simulation = SimulationProvider(repository, settings)
        self.external = OpenMeteoLiveProvider(repository, settings)

    def get_live_snapshot(self, site_id: int) -> LiveResponse:
        cached_snapshot = _SITE_SNAPSHOT_CACHE.get(site_id)
        if cached_snapshot is not None and datetime.utcnow() - cached_snapshot[0] < timedelta(seconds=_CACHE_TTL_SECONDS):
            return cached_snapshot[1]

        if self.settings.live_source_mode == "simulation":
            snapshot = self.simulation.get_snapshot(site_id)
            _SITE_SNAPSHOT_CACHE[site_id] = (datetime.utcnow(), snapshot)
            return snapshot
        try:
            snapshot = self.external.get_snapshot(site_id)
        except Exception:
            cached = self.external.cached_snapshot(site_id)
            if cached is not None:
                _SITE_SNAPSHOT_CACHE[site_id] = (datetime.utcnow(), cached)
                return cached
            fallback = self.simulation.get_snapshot(site_id)
            fallback.fallback_used = True
            fallback.source_label = "Replay simulator fallback after external provider failure"
            _SITE_SNAPSHOT_CACHE[site_id] = (datetime.utcnow(), fallback)
            return fallback

        _SITE_SNAPSHOT_CACHE[site_id] = (datetime.utcnow(), snapshot)
        return snapshot

    def get_live_network(self, scope: str = "india") -> LiveNetworkResponse:
        cached_network = _NETWORK_SNAPSHOT_CACHE.get(scope)
        if cached_network is not None and datetime.utcnow() - cached_network[0] < timedelta(seconds=_CACHE_TTL_SECONDS):
            return cached_network[1]

        catalog = INDIA_LIVE_NETWORK if scope == "india" else (*INDIA_LIVE_NETWORK[:3], *GLOBAL_LIVE_NETWORK)
        locations: list[LiveNetworkLocation] = []
        for location in catalog:
            try:
                locations.append(self.external.get_network_snapshot(location))
            except Exception:
                cached = self.external.cached_network_snapshot(location)
                if cached is not None:
                    locations.append(cached)
        response = LiveNetworkResponse(scope=scope, generated_at=datetime.utcnow(), locations=locations)
        _NETWORK_SNAPSHOT_CACHE[scope] = (datetime.utcnow(), response)
        return response
