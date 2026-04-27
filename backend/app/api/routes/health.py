from fastapi import APIRouter, Depends

from backend.app.core.dependencies import get_app_settings
from backend.app.core.runtime import validate_runtime
from backend.app.schemas.api import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health(settings=Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(status="ok", app_name=settings.app_name, environment=settings.app_env)


@router.get("/ready")
def ready(settings=Depends(get_app_settings)) -> dict:
    status = validate_runtime(settings)
    return {"ready": status.ready, "checks": status.checks}
