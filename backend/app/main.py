"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.database import create_engine
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware, RequestLoggingMiddleware
from app.core.redis import create_redis_client


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    app_settings = settings or get_settings()
    configure_logging(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.db_engine = create_engine(app_settings.DATABASE_URL)
        app.state.redis_client = create_redis_client(app_settings.REDIS_URL)
        try:
            yield
        finally:
            await app.state.redis_client.aclose()
            await app.state.db_engine.dispose()

    application = FastAPI(
        title=f"{app_settings.APP_NAME} Admission API",
        version=__version__,
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(RequestIDMiddleware)
    application.include_router(health_router)
    return application


app = create_app()
