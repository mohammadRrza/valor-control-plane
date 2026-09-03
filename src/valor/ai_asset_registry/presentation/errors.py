"""HTTP mappings for AI Asset Registry failures."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from valor.ai_asset_registry.application.errors import (
    AgentNameAlreadyExists,
    AgentNotFound,
    OwningTenantNotFound,
)
from valor.ai_asset_registry.domain.errors import InvalidAgentName
from valor.api.errors import problem_response


def install_ai_asset_registry_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidAgentName)
    async def invalid_agent_name(request: Request, exc: InvalidAgentName) -> JSONResponse:
        return problem_response(
            request,
            title="Invalid Agent Name",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    @app.exception_handler(AgentNameAlreadyExists)
    async def duplicate_agent_name(request: Request, exc: AgentNameAlreadyExists) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Agent Name Already Exists",
            status_code=status.HTTP_409_CONFLICT,
            detail="An Agent with the same normalized name already exists for this tenant.",
        )

    @app.exception_handler(OwningTenantNotFound)
    async def owning_tenant_not_found(request: Request, exc: OwningTenantNotFound) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Owning Tenant Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested owning tenant was not found.",
        )

    @app.exception_handler(AgentNotFound)
    async def agent_not_found(request: Request, exc: AgentNotFound) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Agent Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested Agent was not found.",
        )
