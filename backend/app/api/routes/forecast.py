from fastapi import APIRouter, Depends

from backend.app.core.dependencies import get_alert_service, get_forecast_service, get_repository
from backend.app.schemas.api import AlertsResponse, ForecastRequest, ForecastResponse, ModelMetadataResponse
from backend.app.services.alert_service import AlertService
from backend.app.services.forecast_service import ForecastService
from backend.app.services.repository import DataRepository

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.post("", response_model=ForecastResponse)
def create_forecast(
    request: ForecastRequest, service: ForecastService = Depends(get_forecast_service)
) -> ForecastResponse:
    return service.generate_forecast(request)


@router.get("/metadata", response_model=ModelMetadataResponse)
def model_metadata(repository: DataRepository = Depends(get_repository)) -> ModelMetadataResponse:
    return ModelMetadataResponse.model_validate(repository.metadata)


@router.get("/alerts", response_model=AlertsResponse)
def alerts(site_id: int | None = None, service: AlertService = Depends(get_alert_service)) -> AlertsResponse:
    return service.current_alerts(site_id)

