from fastapi import Header, HTTPException

from backend.app.core.config import Settings, get_settings
from backend.app.services.auth_service import AuthService
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.alert_service import AlertService
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.forecast_service import ForecastService
from backend.app.services.groq_client import GroqClient
from backend.app.services.live_provider import LiveDataService
from backend.app.services.research_agent import ResearchAgent
from backend.app.services.research_context import ResearchContextBuilder
from backend.app.services.research_service import ResearchService
from backend.app.services.research_store import ResearchStore
from backend.app.services.repository import DataRepository


def get_repository() -> DataRepository:
    return DataRepository(get_settings())


def get_research_store() -> ResearchStore:
    return ResearchStore(get_settings().app_db_path)


def get_forecast_service() -> ForecastService:
    repository = get_repository()
    return ForecastService(repository, get_settings())


def get_analytics_service() -> AnalyticsService:
    repository = get_repository()
    return AnalyticsService(repository)


def get_alert_service() -> AlertService:
    repository = get_repository()
    return AlertService(repository, get_settings())


def get_live_service() -> LiveDataService:
    repository = get_repository()
    return LiveDataService(repository, get_settings())


def get_app_settings() -> Settings:
    return get_settings()


def get_auth_service() -> AuthService:
    return AuthService(get_research_store())


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    token = authorization.removeprefix("Bearer ").strip()
    user = get_research_store().user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid bearer token.")
    return {"token": token, "user": user}


def get_research_service() -> ResearchService:
    settings = get_settings()
    repository = get_repository()
    store = get_research_store()
    return ResearchService(
        store=store,
        repository=repository,
        settings=settings,
        analytics=AnalyticsService(repository),
        forecast_service=ForecastService(repository, settings),
        alert_service=AlertService(repository, settings),
        live_service=LiveDataService(repository, settings),
        context_builder=ResearchContextBuilder(repository, settings),
        agent=ResearchAgent(
            groq_client=GroqClient(settings.groq_api_key, settings.groq_model),
            embedding_service=EmbeddingService(settings.embedding_model),
        ),
    )
