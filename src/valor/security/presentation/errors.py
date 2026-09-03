"""Sanitized HTTP mapping for management authentication failure."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from valor.api.errors import problem_response
from valor.security.application.errors import (
    ManagementAuthenticationFailed,
    RuntimeAuthenticationFailed,
)


def install_security_error_handlers(app: FastAPI) -> None:
    def unauthorized(request: Request) -> JSONResponse:
        response = problem_response(
            request,
            title="Unauthorized",
            status_code=401,
            detail="Authentication credentials are missing or invalid.",
        )
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    @app.exception_handler(ManagementAuthenticationFailed)
    async def authentication_failed(
        request: Request, exc: ManagementAuthenticationFailed
    ) -> JSONResponse:
        del exc
        return unauthorized(request)

    @app.exception_handler(RuntimeAuthenticationFailed)
    async def runtime_authentication_failed(
        request: Request, exc: RuntimeAuthenticationFailed
    ) -> JSONResponse:
        del exc
        return unauthorized(request)
