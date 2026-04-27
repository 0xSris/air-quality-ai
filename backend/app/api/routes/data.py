from fastapi import APIRouter, Depends, Query

from backend.app.core.dependencies import get_analytics_service, get_live_service
from backend.app.schemas.api import DatasetSummaryResponse, LiveNetworkResponse, LiveResponse, TrendResponse
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.live_provider import LiveDataService

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/summary", response_model=DatasetSummaryResponse)
def dataset_summary(service: AnalyticsService = Depends(get_analytics_service)) -> DatasetSummaryResponse:
    return service.dataset_summary()


@router.get("/historical/{site_id}", response_model=TrendResponse)
def historical_trend(
    site_id: int,
    hours: int = Query(default=168, ge=24, le=720),
    service: AnalyticsService = Depends(get_analytics_service),
) -> TrendResponse:
    return service.historical_trend(site_id, hours=hours)


@router.get("/live/{site_id}", response_model=LiveResponse)
def live_data(site_id: int, service: LiveDataService = Depends(get_live_service)) -> LiveResponse:
    return service.get_live_snapshot(site_id)


@router.get("/live-network", response_model=LiveNetworkResponse)
def live_network(
    scope: str = Query(default="india", pattern="^(india|global)$"),
    service: LiveDataService = Depends(get_live_service),
) -> LiveNetworkResponse:
    return service.get_live_network(scope=scope)
