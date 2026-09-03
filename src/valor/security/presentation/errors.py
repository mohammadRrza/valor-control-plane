"""Sanitized HTTP mapping for management authentication failure."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from valor.api.errors import problem_response
from valor.security.application.errors import ManagementAuthenticationFailed


def install_security_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ManagementAuthenticationFailed)
    async def authentication_failed(
        request: Request, exc: ManagementAuthenticationFailed
    ) -> JSONResponse:
        del exc
        response = problem_response(
            request,
            title="Unauthorized",
            status_code=401,
            detail="Authentication credentials are missing or invalid.",
        )
        response.headers["WWW-Authenticate"] = "Bearer"
        return response
