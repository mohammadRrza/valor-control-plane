from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from valor.api.errors import problem_response
from valor.management_identity.application.errors import (
    BootstrapAlreadyCompleted,
    BootstrapAuthenticationFailed,
    InvalidManagementIdentityCommand,
    LastPrincipalManagerConflict,
    ManagementCredentialNotFound,
    ManagementPrincipalNotFound,
    PrincipalManagementDenied,
)


def install_management_identity_error_handlers(app: FastAPI) -> None:
    def unauthorized(request: Request) -> JSONResponse:
        response = problem_response(
            request,
            title="Unauthorized",
            status_code=401,
            detail="Authentication credentials are missing or invalid.",
        )
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    @app.exception_handler(BootstrapAuthenticationFailed)
    async def bootstrap_auth_failed(
        request: Request, exc: BootstrapAuthenticationFailed
    ) -> JSONResponse:
        del exc
        return unauthorized(request)

    @app.exception_handler(BootstrapAlreadyCompleted)
    async def bootstrap_complete(request: Request, exc: BootstrapAlreadyCompleted) -> JSONResponse:
        del exc
        return unauthorized(request)

    async def not_found(request: Request) -> JSONResponse:
        return problem_response(
            request,
            title="Management Identity Not Found",
            status_code=404,
            detail="The requested Management identity resource was not found.",
        )

    @app.exception_handler(ManagementPrincipalNotFound)
    async def principal_not_found(
        request: Request, exc: ManagementPrincipalNotFound
    ) -> JSONResponse:
        del exc
        return await not_found(request)

    @app.exception_handler(ManagementCredentialNotFound)
    async def credential_not_found(
        request: Request, exc: ManagementCredentialNotFound
    ) -> JSONResponse:
        del exc
        return await not_found(request)

    @app.exception_handler(PrincipalManagementDenied)
    async def management_denied(request: Request, exc: PrincipalManagementDenied) -> JSONResponse:
        del exc
        return await not_found(request)

    @app.exception_handler(InvalidManagementIdentityCommand)
    async def invalid_command(
        request: Request, exc: InvalidManagementIdentityCommand
    ) -> JSONResponse:
        return problem_response(
            request,
            title="Invalid Management Identity Command",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    @app.exception_handler(LastPrincipalManagerConflict)
    async def last_manager(request: Request, exc: LastPrincipalManagerConflict) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Management Recovery Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail="The operation would remove the last recoverable Management principal manager.",
        )
