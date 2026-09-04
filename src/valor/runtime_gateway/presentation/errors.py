"""HTTP mappings for Runtime Gateway failures."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from valor.api.errors import problem_response
from valor.runtime_gateway.application.errors import (
    AgentNotAvailable,
    InvocationDenied,
    InvocationNotFound,
    InvocationUsageLimited,
    ModelNotAvailable,
    ProviderInvocationFailed,
    ProviderNotSupportedForRuntime,
    TenantNotAvailable,
    UsageLimitUnavailable,
)
from valor.runtime_gateway.domain.errors import InvalidInvocationInput


def install_runtime_gateway_error_handlers(app: FastAPI) -> None:
    async def unavailable_resource(request: Request) -> JSONResponse:
        return problem_response(
            request,
            title="Runtime Resource Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A requested runtime resource was not found for this tenant.",
        )

    @app.exception_handler(TenantNotAvailable)
    async def tenant_not_available(request: Request, exc: TenantNotAvailable) -> JSONResponse:
        del exc
        return await unavailable_resource(request)

    @app.exception_handler(AgentNotAvailable)
    async def agent_not_available(request: Request, exc: AgentNotAvailable) -> JSONResponse:
        del exc
        return await unavailable_resource(request)

    @app.exception_handler(ModelNotAvailable)
    async def model_not_available(request: Request, exc: ModelNotAvailable) -> JSONResponse:
        del exc
        return await unavailable_resource(request)

    @app.exception_handler(InvalidInvocationInput)
    async def invalid_input(request: Request, exc: InvalidInvocationInput) -> JSONResponse:
        return problem_response(
            request,
            title="Invalid Invocation Input",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )

    @app.exception_handler(ProviderNotSupportedForRuntime)
    async def unsupported_provider(
        request: Request, exc: ProviderNotSupportedForRuntime
    ) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Provider Not Supported for Runtime",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The governed Model provider is not supported for runtime invocation.",
        )

    @app.exception_handler(ProviderInvocationFailed)
    async def provider_failed(request: Request, exc: ProviderInvocationFailed) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Model Provider Invocation Failed",
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The upstream model provider could not complete the invocation.",
        )

    @app.exception_handler(InvocationNotFound)
    async def invocation_not_found(request: Request, exc: InvocationNotFound) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Invocation Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested Invocation was not found.",
        )

    @app.exception_handler(InvocationDenied)
    async def invocation_denied(request: Request, exc: InvocationDenied) -> JSONResponse:
        return problem_response(
            request,
            title="Invocation Denied",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The requested invocation is not permitted.",
            decision_id=exc.decision_id.value,
        )

    @app.exception_handler(InvocationUsageLimited)
    async def invocation_limited(request: Request, exc: InvocationUsageLimited) -> JSONResponse:
        return problem_response(
            request,
            title="Runtime Usage Limit Reached",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Runtime usage allowance for the current UTC day has been exhausted.",
            invocation_id=exc.invocation_id.value,
            window_end=exc.window_end,
        )

    @app.exception_handler(UsageLimitUnavailable)
    async def usage_limit_unavailable(request: Request, exc: UsageLimitUnavailable) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Runtime Usage Check Unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runtime usage could not be verified safely.",
        )
