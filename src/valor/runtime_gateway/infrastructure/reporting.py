"""PostgreSQL aggregation adapter for Tenant Runtime reports."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.identity_tenancy.infrastructure.models import TenantRow
from valor.runtime_gateway.application.reporting import (
    EstimatedCostTotals,
    InvocationCounts,
    RuntimeReportUnavailable,
    TenantRuntimeReport,
    UsageTotals,
)
from valor.runtime_gateway.domain.identity import TenantId
from valor.runtime_gateway.infrastructure.models import InvocationRow

ZERO_COST = Decimal("0.000000000000")


class PostgresTenantRuntimeReportReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def tenant_exists(self, tenant_id: TenantId) -> bool:
        try:
            async with self._session_factory() as session:
                statement = select(TenantRow.id).where(TenantRow.id == tenant_id.value)
                return await session.scalar(statement) is not None
        except SQLAlchemyError as error:
            raise RuntimeReportUnavailable from error

    async def get_report(
        self, *, tenant_id: TenantId, start: datetime, end: datetime
    ) -> TenantRuntimeReport:
        provider_executed = InvocationRow.status.in_(("succeeded", "failed"))
        usage_known = (
            provider_executed
            & InvocationRow.input_units.is_not(None)
            & InvocationRow.output_units.is_not(None)
            & InvocationRow.total_units.is_not(None)
        )
        successful = InvocationRow.status == "succeeded"
        cost_known = successful & InvocationRow.cost_total.is_not(None)
        statement = select(
            func.count(),
            func.count().filter(InvocationRow.status == "succeeded"),
            func.count().filter(InvocationRow.status == "failed"),
            func.count().filter(InvocationRow.status == "denied"),
            func.count().filter(InvocationRow.status == "limited"),
            func.coalesce(func.sum(case((usage_known, InvocationRow.input_units), else_=0)), 0),
            func.coalesce(func.sum(case((usage_known, InvocationRow.output_units), else_=0)), 0),
            func.coalesce(func.sum(case((usage_known, InvocationRow.total_units), else_=0)), 0),
            func.count().filter(provider_executed),
            func.count().filter(usage_known),
            func.count().filter(provider_executed & ~usage_known),
            func.coalesce(
                func.sum(case((cost_known, InvocationRow.cost_total), else_=None)), ZERO_COST
            ),
            func.count().filter(cost_known),
            func.count().filter(successful & ~cost_known),
        ).where(
            InvocationRow.tenant_id == tenant_id.value,
            InvocationRow.started_at >= start,
            InvocationRow.started_at < end,
        )
        try:
            async with self._session_factory() as session:
                row = (await session.execute(statement)).one()
        except SQLAlchemyError as error:
            raise RuntimeReportUnavailable from error
        return TenantRuntimeReport(
            tenant_id,
            start,
            end,
            InvocationCounts(*map(int, row[0:5])),
            UsageTotals(*map(int, row[5:11])),
            EstimatedCostTotals("USD", Decimal(row[11]), int(row[12]), int(row[13])),
        )
