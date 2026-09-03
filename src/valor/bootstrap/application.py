"""FastAPI composition root and resource lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from valor.ai_asset_registry.infrastructure.model_unit_of_work import SqlAlchemyModelUnitOfWork
from valor.ai_asset_registry.infrastructure.tenant_existence import PostgresTenantExistence
from valor.ai_asset_registry.infrastructure.unit_of_work import SqlAlchemyAgentUnitOfWork
from valor.ai_asset_registry.presentation.errors import install_ai_asset_registry_error_handlers
from valor.ai_asset_registry.presentation.model_routes import router as model_router
from valor.ai_asset_registry.presentation.routes import router as agent_router
from valor.api.errors import install_error_handlers
from valor.api.health import router as health_router
from valor.bootstrap.database import create_database_resources
from valor.bootstrap.logging import configure_logging
from valor.bootstrap.settings import Settings, get_settings
from valor.identity_tenancy.infrastructure.unit_of_work import SqlAlchemyTenantUnitOfWork
from valor.identity_tenancy.presentation.errors import install_identity_tenancy_error_handlers
from valor.identity_tenancy.presentation.routes import router as tenant_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.observability)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = create_database_resources(resolved.database)
        app.state.database = database
        app.state.tenant_unit_of_work_factory = partial(
            SqlAlchemyTenantUnitOfWork, database.sessions
        )
        app.state.agent_unit_of_work_factory = partial(SqlAlchemyAgentUnitOfWork, database.sessions)
        app.state.model_unit_of_work_factory = partial(SqlAlchemyModelUnitOfWork, database.sessions)
        app.state.tenant_existence_factory = partial(PostgresTenantExistence, database.sessions)
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
    app.include_router(tenant_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(model_router, prefix="/api/v1")
    install_error_handlers(app)
    install_identity_tenancy_error_handlers(app)
    install_ai_asset_registry_error_handlers(app)
    return app
