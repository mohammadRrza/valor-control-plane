from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from valor.api.errors import problem_response
from valor.policy_risk.application.errors import (
    PermissionNotFound,
    PolicyAgentNotAvailable,
    PolicyModelNotAvailable,
    PolicyTenantNotAvailable,
)


def install_policy_error_handlers(app: FastAPI) -> None:
    async def unavailable(request: Request) -> JSONResponse:
        return problem_response(
            request,
            title="Policy Resource Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A requested policy resource was not found for this tenant.",
        )

    @app.exception_handler(PolicyTenantNotAvailable)
    async def tenant_missing(request: Request, exc: PolicyTenantNotAvailable) -> JSONResponse:
        del exc
        return await unavailable(request)

    @app.exception_handler(PolicyAgentNotAvailable)
    async def agent_missing(request: Request, exc: PolicyAgentNotAvailable) -> JSONResponse:
        del exc
        return await unavailable(request)

    @app.exception_handler(PolicyModelNotAvailable)
    async def model_missing(request: Request, exc: PolicyModelNotAvailable) -> JSONResponse:
        del exc
        return await unavailable(request)

    @app.exception_handler(PermissionNotFound)
    async def permission_missing(request: Request, exc: PermissionNotFound) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Permission Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested Agent-to-Model permission was not found.",
        )
