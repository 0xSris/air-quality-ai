from __future__ import annotations

from backend.app.core.config import Settings
from backend.app.schemas.api import AlertItem, AlertsResponse, ForecastRequest
from backend.app.services.forecast_service import ForecastService
from backend.app.services.repository import DataRepository


class AlertService:
    def __init__(self, repository: DataRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def current_alerts(self, site_id: int | None = None) -> AlertsResponse:
        site_ids = [site_id] if site_id is not None else [site["site_id"] for site in self.repository.dataset_summary["sites"]]
        alerts: list[AlertItem] = []
        forecast_service = ForecastService(self.repository, self.settings)
        for current_site in site_ids:
            forecast = forecast_service.generate_forecast(ForecastRequest(site_id=current_site, horizon_hours=12))
            for point in forecast.points:
                if point.o3 >= self.settings.alert_o3_threshold:
                    alerts.append(
                        AlertItem(
                            site_id=current_site,
                            pollutant="O3",
                            severity="critical" if point.o3 >= self.settings.alert_o3_threshold * 1.2 else "warning",
                            message="Projected O3 spike exceeds configured threshold.",
                            timestamp=point.timestamp,
                            value=point.o3,
                            threshold=self.settings.alert_o3_threshold,
                        )
                    )
                if point.no2 >= self.settings.alert_no2_threshold:
                    alerts.append(
                        AlertItem(
                            site_id=current_site,
                            pollutant="NO2",
                            severity="critical" if point.no2 >= self.settings.alert_no2_threshold * 1.2 else "warning",
                            message="Projected NO2 spike exceeds configured threshold.",
                            timestamp=point.timestamp,
                            value=point.no2,
                            threshold=self.settings.alert_no2_threshold,
                        )
                    )
        alerts.sort(key=lambda item: (item.timestamp, item.site_id))
        return AlertsResponse(site_id=site_id, alerts=alerts)

