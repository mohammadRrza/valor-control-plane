"""FastAPI composition root and resource lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from valor.api.errors import install_error_handlers
from valor.api.health import router as health_router
from valor.bootstrap.database import create_database_resources
from valor.bootstrap.logging import configure_logging
from valor.bootstrap.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.observability)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = create_database_resources(resolved.database)
        app.state.database = database
        yield
        await database.close()

    app = FastAPI(
        title=resolved.application.name,
        version="0.1.0",
        debug=resolved.application.debug,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.include_router(health_router)
    app.include_router(APIRouter(prefix="/api/v1"))
    install_error_handlers(app)
    return app
