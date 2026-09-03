"""HTTP mappings for Identity and Tenancy failures."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from valor.api.errors import problem_response
from valor.identity_tenancy.application.errors import TenantNameAlreadyExists, TenantNotFound
from valor.identity_tenancy.domain.errors import InvalidTenantName


def install_identity_tenancy_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidTenantName)
    async def invalid_tenant_name(request: Request, exc: InvalidTenantName) -> JSONResponse:
        return problem_response(
            request,
            title="Invalid Tenant Name",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    @app.exception_handler(TenantNameAlreadyExists)
    async def duplicate_tenant_name(request: Request, exc: TenantNameAlreadyExists) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Tenant Name Already Exists",
            status_code=status.HTTP_409_CONFLICT,
            detail="A tenant with the same normalized name already exists.",
        )

    @app.exception_handler(TenantNotFound)
    async def tenant_not_found(request: Request, exc: TenantNotFound) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Tenant Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested tenant was not found.",
        )
