"""Static Tenant budget configuration and PostgreSQL cost aggregation adapters."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.bootstrap.settings import TenantBudgetSettings
from valor.runtime_gateway.application.errors import TenantCostBudgetCheckUnavailable
from valor.runtime_gateway.domain.cost_budget import TenantCostBudget
from valor.runtime_gateway.domain.identity import TenantId
from valor.runtime_gateway.infrastructure.models import InvocationRow


class ConfiguredTenantCostBudgets:
    def __init__(self, settings: TenantBudgetSettings) -> None:
        self._budgets = {
            entry.tenant_id: TenantCostBudget(
                entry.daily_estimated_cost_budget,
                entry.per_invocation_cost_allowance,
                entry.currency,
            )
            for entry in settings.entries
        }

    def resolve(self, tenant_id: TenantId) -> TenantCostBudget | None:
        return self._budgets.get(tenant_id.value)


class PostgresTenantEstimatedCostReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def attributed_cost(
        self, *, tenant_id: TenantId, window_start: datetime, window_end: datetime
    ) -> Decimal:
        try:
            async with self._sessions() as session:
                cost = await session.scalar(
                    select(func.coalesce(func.sum(InvocationRow.cost_total), Decimal("0"))).where(
                        InvocationRow.tenant_id == tenant_id.value,
                        InvocationRow.started_at >= window_start,
                        InvocationRow.started_at < window_end,
                        InvocationRow.cost_total.is_not(None),
                    )
                )
        except SQLAlchemyError as error:
            raise TenantCostBudgetCheckUnavailable from error
        return Decimal(cost or 0)
