from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from valor.api.errors import problem_response
from valor.runtime_identity.application.errors import (
    InvalidRuntimeIdentityCommand,
    RuntimeBindingNotFound,
    RuntimeCredentialNotFound,
    RuntimeIdentityContinuityConflict,
    RuntimePrincipalManagementDenied,
    RuntimePrincipalNotFound,
    RuntimeUsageLimitsAlreadyInitialized,
)


def install_runtime_identity_error_handlers(app: FastAPI) -> None:
    async def hidden(request: Request, exc: Exception) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Runtime Identity Not Found",
            status_code=404,
            detail="The requested Runtime identity resource was not found.",
        )

    for error in (
        RuntimeBindingNotFound,
        RuntimeCredentialNotFound,
        RuntimePrincipalManagementDenied,
        RuntimePrincipalNotFound,
    ):
        app.add_exception_handler(error, hidden)

    @app.exception_handler(InvalidRuntimeIdentityCommand)
    async def invalid(request: Request, exc: InvalidRuntimeIdentityCommand) -> JSONResponse:
        return problem_response(
            request,
            title="Invalid Runtime Identity Command",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    @app.exception_handler(RuntimeUsageLimitsAlreadyInitialized)
    async def conflict(request: Request, exc: RuntimeUsageLimitsAlreadyInitialized) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Runtime Usage Limits Already Initialized",
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime usage limits can only be initialized once.",
        )

    @app.exception_handler(RuntimeIdentityContinuityConflict)
    async def continuity_conflict(
        request: Request, exc: RuntimeIdentityContinuityConflict
    ) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Runtime Identity Continuity Conflict",
            status_code=status.HTTP_409_CONFLICT,
            detail="The Runtime identity continuity binding is already claimed.",
        )
