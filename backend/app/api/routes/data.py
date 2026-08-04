from enum import Enum

from fastapi import APIRouter, Depends, Query

from backend.app.core.dependencies import (
    get_analytics_service,
    get_live_service,
)
from backend.app.schemas.api import (
    DatasetSummaryResponse,
    LiveNetworkResponse,
    LiveResponse,
    TrendResponse,
)
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.live_provider import LiveDataService


DEFAULT_HISTORY_HOURS = 168
MIN_HISTORY_HOURS = 24
MAX_HISTORY_HOURS = 720


class Scope(str, Enum):
    india = "india"
    global_ = "global"


router = APIRouter(prefix="/data", tags=["data"])


@router.get(
    "/summary",
    response_model=DatasetSummaryResponse,
    status_code=200,
    summary="Dataset Summary",
)
def dataset_summary(
    service: AnalyticsService = Depends(get_analytics_service),
) -> DatasetSummaryResponse:
    """Return summary statistics for the available dataset."""
    return service.dataset_summary()


@router.get(
    "/historical/{site_id}",
    response_model=TrendResponse,
    status_code=200,
    summary="Historical Trend",
)
def historical_trend(
    site_id: int,
    hours: int = Query(
        default=DEFAULT_HISTORY_HOURS,
        ge=MIN_HISTORY_HOURS,
        le=MAX_HISTORY_HOURS,
        description="Number of hours of historical data to return.",
    ),
    service: AnalyticsService = Depends(get_analytics_service),
) -> TrendResponse:
    """Return historical trend data for a specific site."""
    return service.historical_trend(site_id, hours=hours)


@router.get(
    "/live/{site_id}",
    response_model=LiveResponse,
    status_code=200,
    summary="Live Site Data",
)
def live_data(
    site_id: int,
    service: LiveDataService = Depends(get_live_service),
) -> LiveResponse:
    """Return the latest live metrics for a specific site."""
    return service.get_live_snapshot(site_id)


@router.get(
    "/live-network",
    response_model=LiveNetworkResponse,
    status_code=200,
    summary="Live Network Data",
)
def live_network(
    scope: Scope = Query(
        default=Scope.india,
        description="Network scope.",
    ),
    service: LiveDataService = Depends(get_live_service),
) -> LiveNetworkResponse:
    """Return live metrics aggregated across the selected network."""
    return service.get_live_network(scope=scope.value)
