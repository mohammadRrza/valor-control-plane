"""Operational health endpoints, separate from domain APIs."""

from typing import Annotated, cast

import structlog
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger(__name__)


class HealthStatus(BaseModel):
    status: str


def database_engine(request: Request) -> AsyncEngine:
    return cast(AsyncEngine, request.app.state.database.engine)


router = APIRouter(prefix="/health", tags=["operations"])


@router.get("/live", response_model=HealthStatus)
async def liveness() -> HealthStatus:
    return HealthStatus(status="alive")


@router.get(
    "/ready",
    response_model=HealthStatus,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthStatus}},
)
async def readiness(
    engine: Annotated[AsyncEngine, Depends(database_engine)],
) -> HealthStatus | JSONResponse:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("database_readiness_failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthStatus(status="unavailable").model_dump(),
        )
    return HealthStatus(status="ready")
