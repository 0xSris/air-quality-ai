from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import auth, data, forecast, health, research
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.core.runtime import validate_runtime

configure_logging()
settings = get_settings()
runtime_status = validate_runtime(settings)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000", "http://localhost:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):517[0-9]",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(data.router)
app.include_router(forecast.router)
app.include_router(research.router)
app.state.runtime_status = runtime_status
