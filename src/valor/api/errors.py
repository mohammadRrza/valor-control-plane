"""Consistent HTTP error representation at the presentation boundary."""

from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    decision_id: UUID | None = None
    invocation_id: UUID | None = None
    window_end: datetime | None = None


def problem_response(
    request: Request,
    *,
    title: str,
    status_code: int,
    detail: str,
    decision_id: UUID | None = None,
    invocation_id: UUID | None = None,
    window_end: datetime | None = None,
) -> JSONResponse:
    problem = ProblemDetail(
        title=title,
        status=status_code,
        detail=detail,
        instance=request.url.path,
        decision_id=decision_id,
        invocation_id=invocation_id,
        window_end=window_end,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Request Validation Failed",
            status_code=422,
            detail="The request did not satisfy the API contract.",
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        del exc
        return problem_response(
            request,
            title="Internal Server Error",
            status_code=500,
            detail="An unexpected error occurred.",
        )
