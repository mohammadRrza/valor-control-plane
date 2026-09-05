"""PostgreSQL aggregation adapter for Tenant Runtime reports."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql import Select

from valor.identity_tenancy.infrastructure.models import TenantRow
from valor.runtime_gateway.application.reporting import (
    TOP_N,
    AgentCostBreakdown,
    EstimatedCostTotals,
    InvocationCounts,
    ModelCostBreakdown,
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
            func.count().filter(InvocationRow.status == "cost_limited"),
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
                agent_rows = await self._agent_breakdown(session, tenant_id, start, end)
                model_rows = await self._model_breakdown(session, tenant_id, start, end)
        except SQLAlchemyError as error:
            raise RuntimeReportUnavailable from error
        return TenantRuntimeReport(
            tenant_id,
            start,
            end,
            InvocationCounts(*map(int, row[0:6])),
            UsageTotals(*map(int, row[6:12])),
            EstimatedCostTotals("USD", Decimal(row[12]), int(row[13]), int(row[14])),
            tuple(
                AgentCostBreakdown(
                    item[0],
                    int(item[1]),
                    int(item[2]),
                    int(item[3]),
                    int(item[4]),
                    Decimal(item[5]),
                    int(item[6]),
                    int(item[7]),
                )
                for item in agent_rows[:TOP_N]
            ),
            tuple(
                ModelCostBreakdown(
                    item[0],
                    int(item[1]),
                    int(item[2]),
                    int(item[3]),
                    int(item[4]),
                    Decimal(item[5]),
                    int(item[6]),
                    int(item[7]),
                )
                for item in model_rows[:TOP_N]
            ),
            len(agent_rows) > TOP_N,
            len(model_rows) > TOP_N,
        )

    async def _agent_breakdown(
        self, session: AsyncSession, tenant_id: TenantId, start: datetime, end: datetime
    ) -> list[tuple[UUID, int, int, int, int, Decimal, int, int]]:
        statement = self._breakdown_statement(InvocationRow.agent_id, tenant_id, start, end)
        return list((await session.execute(statement)).tuples().all())

    async def _model_breakdown(
        self, session: AsyncSession, tenant_id: TenantId, start: datetime, end: datetime
    ) -> list[tuple[UUID, int, int, int, int, Decimal, int, int]]:
        statement = self._breakdown_statement(InvocationRow.model_id, tenant_id, start, end)
        return list((await session.execute(statement)).tuples().all())

    @staticmethod
    def _breakdown_statement(
        identity_column: InstrumentedAttribute[UUID],
        tenant_id: TenantId,
        start: datetime,
        end: datetime,
    ) -> Select[tuple[UUID, int, int, int, int, Decimal, int, int]]:
        provider_executed = InvocationRow.status.in_(("succeeded", "failed"))
        usage_known = (
            provider_executed
            & InvocationRow.input_units.is_not(None)
            & InvocationRow.output_units.is_not(None)
            & InvocationRow.total_units.is_not(None)
        )
        successful = InvocationRow.status == "succeeded"
        cost_known = successful & InvocationRow.cost_total.is_not(None)
        estimated_cost_total = func.coalesce(
            func.sum(case((cost_known, InvocationRow.cost_total), else_=None)), ZERO_COST
        )
        return (
            select(
                identity_column,
                func.count(),
                func.coalesce(func.sum(case((usage_known, InvocationRow.total_units), else_=0)), 0),
                func.count().filter(usage_known),
                func.count().filter(provider_executed & ~usage_known),
                estimated_cost_total,
                func.count().filter(cost_known),
                func.count().filter(successful & ~cost_known),
            )
            .where(
                InvocationRow.tenant_id == tenant_id.value,
                InvocationRow.started_at >= start,
                InvocationRow.started_at < end,
            )
            .group_by(identity_column)
            .order_by(estimated_cost_total.desc(), identity_column.asc())
            .limit(TOP_N + 1)
        )
