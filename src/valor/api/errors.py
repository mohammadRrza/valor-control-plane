"""Consistent HTTP error representation at the presentation boundary."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        del exc
        problem = ProblemDetail(
            title="Internal Server Error",
            status=500,
            detail="An unexpected error occurred.",
            instance=str(request.url.path),
        )
        return JSONResponse(
            status_code=500,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )
