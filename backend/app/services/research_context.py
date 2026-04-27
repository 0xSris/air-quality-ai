from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.core.config import Settings
from backend.app.schemas.api import AlertsResponse, ForecastResponse, LiveNetworkResponse, LiveResponse, TrendResponse
from backend.app.services.repository import DataRepository


@dataclass(slots=True)
class ContextChunk:
    chunk_id: str
    title: str
    source_type: str
    text: str
    url: str | None = None
    credibility: float = 0.7
    metadata: dict[str, Any] | None = None


class ResearchContextBuilder:
    def __init__(self, repository: DataRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def build(
        self,
        *,
        site_id: int,
        trend: TrendResponse,
        live: LiveResponse,
        forecast: ForecastResponse,
        alerts: AlertsResponse,
        live_network: LiveNetworkResponse,
        dashboard_context: dict[str, Any] | None = None,
    ) -> list[ContextChunk]:
        chunks = [
            *(
                [
                    ContextChunk(
                        chunk_id="dashboard_visible_state",
                        title="Visible dashboard state",
                        source_type="dashboard",
                        text=self._dashboard_context_text(dashboard_context),
                        credibility=0.99,
                        metadata=dashboard_context,
                    )
                ]
                if dashboard_context
                else []
            ),
            ContextChunk(
                chunk_id="dataset_summary",
                title="Dataset summary",
                source_type="dataset",
                text=self._dataset_text(site_id),
                credibility=0.95,
                metadata=self._dataset_metadata(site_id),
            ),
            ContextChunk(
                chunk_id="live_station",
                title="Current station conditions",
                source_type="live",
                text=self._live_text(live),
                credibility=0.95,
                metadata=self._live_metadata(live),
            ),
            ContextChunk(
                chunk_id="forecast_station",
                title="Forecast outlook",
                source_type="forecast",
                text=self._forecast_text(forecast, live),
                credibility=0.92,
                metadata=self._forecast_metadata(forecast, live),
            ),
            ContextChunk(
                chunk_id="alerts",
                title="Alert state",
                source_type="alerts",
                text=self._alerts_text(alerts),
                credibility=0.9,
                metadata=self._alerts_metadata(alerts),
            ),
            ContextChunk(
                chunk_id="live_network",
                title="Live network",
                source_type="network",
                text=self._network_text(live_network),
                credibility=0.86,
                metadata=self._network_metadata(live_network),
            ),
            ContextChunk(
                chunk_id="historical_recent",
                title="Recent historical behavior",
                source_type="historical",
                text=self._historical_text(trend),
                credibility=0.88,
                metadata=self._historical_metadata(trend),
            ),
        ]
        chunks.extend(self._document_chunks())
        return chunks

    @staticmethod
    def _dashboard_context_text(context: dict[str, Any] | None) -> str:
        if not context:
            return "No visible dashboard state was attached to this research request."
        selected_city = context.get("selected_city_name") or context.get("selected_city_label") or "no selected city"
        return (
            "The frontend attached the exact visible dashboard state for this investigation. "
            f"Station {context.get('station_label', context.get('site_id', 'unknown'))}; "
            f"selected timestamp {context.get('selected_timestamp', 'sync pending')}; "
            f"visible phase {context.get('phase', 'unknown')}; "
            f"visible O3 {context.get('visible_o3', 'n/a')} ug/m3; "
            f"visible NO2 {context.get('visible_no2', 'n/a')} ug/m3; "
            f"visible risk {context.get('risk', 'unknown')}; "
            f"forecast peak O3 {context.get('forecast_peak_o3', 'n/a')} at {context.get('forecast_peak_o3_time', 'n/a')}; "
            f"forecast peak NO2 {context.get('forecast_peak_no2', 'n/a')} at {context.get('forecast_peak_no2_time', 'n/a')}; "
            f"active city comparison {selected_city}; "
            f"active configured alert count {context.get('alert_count', 0)}."
        )

    def _dataset_text(self, site_id: int) -> str:
        summary = self.repository.dataset_summary
        site = next(site for site in summary["sites"] if site["site_id"] == site_id)
        return (
            f"Selected site {site_id} is located at {site['latitude']}, {site['longitude']}. "
            f"The dataset contains {summary['total_sites']} sites, {summary['total_train_rows']} train rows, "
            f"and {summary['total_unseen_rows']} unseen rows. Features include {', '.join(summary['features'][:12])}. "
            f"Targets are {', '.join(summary['targets'])}."
        )

    def _dataset_metadata(self, site_id: int) -> dict[str, Any]:
        summary = self.repository.dataset_summary
        site = next(site for site in summary["sites"] if site["site_id"] == site_id)
        return {
            "site_id": site_id,
            "latitude": float(site["latitude"]),
            "longitude": float(site["longitude"]),
            "total_sites": int(summary["total_sites"]),
            "total_train_rows": int(summary["total_train_rows"]),
            "total_unseen_rows": int(summary["total_unseen_rows"]),
            "targets": list(summary["targets"]),
        }

    @staticmethod
    def _live_text(live: LiveResponse) -> str:
        return (
            f"Live station feed provider is {live.provider}. Current O3 is {live.current.O3:.1f} ug/m3 and "
            f"current NO2 is {live.current.NO2:.1f} ug/m3. Source label: {live.source_label}. "
            f"Fallback used: {live.fallback_used}. Last updated: {live.last_updated.isoformat()}."
        )

    @staticmethod
    def _live_metadata(live: LiveResponse) -> dict[str, Any]:
        return {
            "provider": live.provider,
            "source_label": live.source_label,
            "fallback_used": bool(live.fallback_used),
            "o3": float(live.current.O3),
            "no2": float(live.current.NO2),
            "us_aqi": float(live.current.us_aqi) if live.current.us_aqi is not None else None,
            "european_aqi": float(live.current.european_aqi) if live.current.european_aqi is not None else None,
            "last_updated": live.last_updated.isoformat(),
        }

    @staticmethod
    def _forecast_text(forecast: ForecastResponse, live: LiveResponse) -> str:
        if not forecast.points:
            return "No forecast points are available."
        peak_o3 = max(point.o3 for point in forecast.points)
        peak_no2 = max(point.no2 for point in forecast.points)
        peak_o3_index = max(range(len(forecast.points)), key=lambda index: forecast.points[index].o3)
        peak_no2_index = max(range(len(forecast.points)), key=lambda index: forecast.points[index].no2)
        return (
            f"Forecast model {forecast.model_name} generated {forecast.horizon_hours} hourly points. "
            f"Peak O3 is {peak_o3:.1f} ug/m3 at forecast hour +{peak_o3_index + 1}. "
            f"Peak NO2 is {peak_no2:.1f} ug/m3 at forecast hour +{peak_no2_index + 1}. "
            f"The forecast window is anchored after live station sync {live.last_updated.isoformat()}. "
            f"Forecast generated at {forecast.generated_at.isoformat()}."
        )

    @staticmethod
    def _forecast_metadata(forecast: ForecastResponse, live: LiveResponse) -> dict[str, Any]:
        if not forecast.points:
            return {"horizon_hours": forecast.horizon_hours, "points": []}
        peak_o3_index = max(range(len(forecast.points)), key=lambda index: forecast.points[index].o3)
        peak_no2_index = max(range(len(forecast.points)), key=lambda index: forecast.points[index].no2)
        peak_o3_point = forecast.points[peak_o3_index]
        peak_no2_point = forecast.points[peak_no2_index]
        return {
            "model_name": forecast.model_name,
            "horizon_hours": forecast.horizon_hours,
            "generated_at": forecast.generated_at.isoformat(),
            "live_anchor": live.last_updated.isoformat(),
            "peak_o3": float(peak_o3_point.o3),
            "peak_o3_hour": peak_o3_index + 1,
            "peak_no2": float(peak_no2_point.no2),
            "peak_no2_hour": peak_no2_index + 1,
            "points": [
                {
                    "lead_hour": index + 1,
                    "o3": float(point.o3),
                    "no2": float(point.no2),
                    "o3_upper": float(point.o3_upper),
                    "o3_lower": float(point.o3_lower),
                    "no2_upper": float(point.no2_upper),
                    "no2_lower": float(point.no2_lower),
                }
                for index, point in enumerate(forecast.points[:24])
            ],
        }

    @staticmethod
    def _alerts_text(alerts: AlertsResponse) -> str:
        if not alerts.alerts:
            return "No current threshold exceedance alerts were generated."
        rendered = [
            f"{alert.pollutant} {alert.severity} at site {alert.site_id}: {alert.message} value {alert.value:.1f} threshold {alert.threshold:.1f}"
            for alert in alerts.alerts[:10]
        ]
        return " ".join(rendered)

    @staticmethod
    def _alerts_metadata(alerts: AlertsResponse) -> dict[str, Any]:
        return {
            "count": len(alerts.alerts),
            "items": [
                {
                    "site_id": int(alert.site_id),
                    "pollutant": alert.pollutant,
                    "severity": alert.severity,
                    "message": alert.message,
                    "value": float(alert.value),
                    "threshold": float(alert.threshold),
                }
                for alert in alerts.alerts[:10]
            ],
        }

    @staticmethod
    def _network_text(live_network: LiveNetworkResponse) -> str:
        if not live_network.locations:
            return "No live network locations are currently available."
        top = sorted(
            live_network.locations,
            key=lambda location: max(location.current.us_aqi or 0, location.current.european_aqi or 0),
            reverse=True,
        )[:8]
        rendered = [
            f"{location.name} {location.country} O3 {location.current.O3:.1f} NO2 {location.current.NO2:.1f} modeled US AQI {location.current.us_aqi or 0:.0f}"
            for location in top
        ]
        return f"Live network scope is {live_network.scope}. " + " ".join(rendered)

    @staticmethod
    def _network_metadata(live_network: LiveNetworkResponse) -> dict[str, Any]:
        top = sorted(
            live_network.locations,
            key=lambda location: max(location.current.us_aqi or 0, location.current.european_aqi or 0),
            reverse=True,
        )[:8]
        return {
            "scope": live_network.scope,
            "count": len(live_network.locations),
            "top_locations": [
                {
                    "key": location.key,
                    "name": location.name,
                    "country": location.country,
                    "o3": float(location.current.O3),
                    "no2": float(location.current.NO2),
                    "us_aqi": float(location.current.us_aqi) if location.current.us_aqi is not None else None,
                    "aqi_label": "modeled US AQI estimate from Open-Meteo CAMS, not CPCB official AQI",
                }
                for location in top
            ],
        }

    @staticmethod
    def _historical_text(trend: TrendResponse) -> str:
        if not trend.points:
            return "No historical trend points are available."
        avg_o3 = sum(point.O3 for point in trend.points) / len(trend.points)
        avg_no2 = sum(point.NO2 for point in trend.points) / len(trend.points)
        return (
            f"Recent history for site {trend.site_id} spans {len(trend.points)} hours. "
            f"Average O3 is {avg_o3:.1f} and average NO2 is {avg_no2:.1f}. "
            f"First timestamp {trend.points[0].timestamp.isoformat()}, last timestamp {trend.points[-1].timestamp.isoformat()}."
        )

    @staticmethod
    def _historical_metadata(trend: TrendResponse) -> dict[str, Any]:
        if not trend.points:
            return {"site_id": trend.site_id, "count": 0}
        avg_o3 = sum(point.O3 for point in trend.points) / len(trend.points)
        avg_no2 = sum(point.NO2 for point in trend.points) / len(trend.points)
        max_o3 = max(point.O3 for point in trend.points)
        max_no2 = max(point.NO2 for point in trend.points)
        return {
            "site_id": trend.site_id,
            "count": len(trend.points),
            "avg_o3": float(avg_o3),
            "avg_no2": float(avg_no2),
            "max_o3": float(max_o3),
            "max_no2": float(max_no2),
            "first_timestamp": trend.points[0].timestamp.isoformat(),
            "last_timestamp": trend.points[-1].timestamp.isoformat(),
        }

    def _document_chunks(self) -> list[ContextChunk]:
        document_paths = [
            Path("README.md"),
            Path("docs/architecture.md"),
            Path("docs/data_dictionary.md"),
        ]
        chunks: list[ContextChunk] = []
        for path in document_paths:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            if not normalized:
                continue
            chunks.append(
                ContextChunk(
                    chunk_id=f"doc:{path.name}",
                    title=path.name,
                    source_type="document",
                    text=normalized[:3500],
                    url=str(path),
                    credibility=0.82,
                )
            )
        return chunks
