from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from valor.api.errors import problem_response
from valor.management_audit.application.query import (
    InvalidAuditRange,
    ManagementAuditUnavailable,
    TenantAuditNotFound,
)


def install_management_audit_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidAuditRange)
    async def invalid_range(request: Request, exc: InvalidAuditRange) -> JSONResponse:
        return problem_response(
            request,
            title="Invalid Audit Range",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    @app.exception_handler(TenantAuditNotFound)
    async def tenant_not_found(request: Request, exc: TenantAuditNotFound) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Tenant Audit Records Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested Tenant audit records were not found.",
        )

    @app.exception_handler(ManagementAuditUnavailable)
    async def unavailable(request: Request, exc: ManagementAuditUnavailable) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Management Audit Unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Management audit records are temporarily unavailable.",
        )
