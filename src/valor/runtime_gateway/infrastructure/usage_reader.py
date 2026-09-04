"""PostgreSQL aggregate reader for Runtime Principal usage."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.runtime_gateway.application.errors import UsageLimitUnavailable
from valor.runtime_gateway.infrastructure.models import InvocationRow


class PostgresRuntimeUsageReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def consumed_total_units(
        self,
        *,
        runtime_principal_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        try:
            async with self._sessions() as session:
                consumed = await session.scalar(
                    select(func.coalesce(func.sum(InvocationRow.total_units), 0)).where(
                        InvocationRow.runtime_principal_id == runtime_principal_id,
                        InvocationRow.started_at >= window_start,
                        InvocationRow.started_at < window_end,
                        InvocationRow.total_units.is_not(None),
                    )
                )
        except SQLAlchemyError as error:
            raise UsageLimitUnavailable from error
        return int(consumed or 0)
