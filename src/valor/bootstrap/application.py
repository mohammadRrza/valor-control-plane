"""FastAPI composition root and resource lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import Depends, FastAPI

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
from valor.policy_risk.infrastructure.admission import PostgresPolicyAdmission
from valor.policy_risk.infrastructure.runtime_policy import RuntimePolicyAdapter
from valor.policy_risk.infrastructure.unit_of_work import SqlAlchemyPolicyUnitOfWork
from valor.policy_risk.presentation.errors import install_policy_error_handlers
from valor.policy_risk.presentation.routes import router as policy_router
from valor.runtime_gateway.application.ports import ModelProviderPort
from valor.runtime_gateway.infrastructure.admission import PostgresRuntimeAdmission
from valor.runtime_gateway.infrastructure.cost_budget import (
    ConfiguredTenantCostBudgets,
    PostgresTenantEstimatedCostReader,
)
from valor.runtime_gateway.infrastructure.openai_provider import OpenAIResponsesProvider
from valor.runtime_gateway.infrastructure.pricing import ConfiguredInvocationPricing
from valor.runtime_gateway.infrastructure.reporting import PostgresTenantRuntimeReportReader
from valor.runtime_gateway.infrastructure.unit_of_work import SqlAlchemyInvocationUnitOfWork
from valor.runtime_gateway.infrastructure.usage_reader import PostgresRuntimeUsageReader
from valor.runtime_gateway.presentation.errors import install_runtime_gateway_error_handlers
from valor.runtime_gateway.presentation.reporting_routes import router as runtime_reporting_router
from valor.runtime_gateway.presentation.routes import router as runtime_router
from valor.security.presentation.authentication import require_management_principal
from valor.security.presentation.errors import install_security_error_handlers


def create_app(
    settings: Settings | None = None,
    *,
    runtime_provider: ModelProviderPort | None = None,
) -> FastAPI:
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
        app.state.invocation_unit_of_work_factory = partial(
            SqlAlchemyInvocationUnitOfWork, database.sessions
        )
        app.state.runtime_admission = PostgresRuntimeAdmission(database.sessions)
        app.state.runtime_usage_reader = PostgresRuntimeUsageReader(database.sessions)
        app.state.runtime_report_reader = PostgresTenantRuntimeReportReader(database.sessions)
        app.state.invocation_pricing = ConfiguredInvocationPricing(resolved.pricing)
        app.state.tenant_cost_budgets = ConfiguredTenantCostBudgets(resolved.tenant_budgets)
        app.state.tenant_cost_reader = PostgresTenantEstimatedCostReader(database.sessions)
        app.state.policy_uow_factory = partial(SqlAlchemyPolicyUnitOfWork, database.sessions)
        app.state.policy_admission = PostgresPolicyAdmission(database.sessions)
        app.state.runtime_policy = RuntimePolicyAdapter(app.state.policy_uow_factory)
        api_key = resolved.provider.openai_api_key
        api_key_value = api_key.get_secret_value() if api_key is not None else None
        app.state.runtime_provider = runtime_provider or OpenAIResponsesProvider(
            api_key_value or None,
            timeout_seconds=resolved.provider.timeout_seconds,
        )
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
    management_auth = [Depends(require_management_principal)]
    app.include_router(tenant_router, prefix="/api/v1", dependencies=management_auth)
    app.include_router(agent_router, prefix="/api/v1", dependencies=management_auth)
    app.include_router(model_router, prefix="/api/v1", dependencies=management_auth)
    app.include_router(runtime_router, prefix="/api/v1")
    app.include_router(runtime_reporting_router, prefix="/api/v1")
    app.include_router(policy_router, prefix="/api/v1", dependencies=management_auth)
    install_error_handlers(app)
    install_identity_tenancy_error_handlers(app)
    install_ai_asset_registry_error_handlers(app)
    install_runtime_gateway_error_handlers(app)
    install_policy_error_handlers(app)
    install_security_error_handlers(app)
    return app
