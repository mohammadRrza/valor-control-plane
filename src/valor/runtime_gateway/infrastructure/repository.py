"""SQLAlchemy Invocation repository adapter."""

from psycopg.errors import ForeignKeyViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from valor.runtime_gateway.application.errors import (
    AgentNotAvailable,
    ModelNotAvailable,
    TenantNotAvailable,
)
from valor.runtime_gateway.domain.cost import InvocationCost
from valor.runtime_gateway.domain.identity import (
    AgentId,
    InvocationId,
    ModelId,
    PolicyDecisionId,
    TenantId,
)
from valor.runtime_gateway.domain.invocation import Invocation, InvocationStatus
from valor.runtime_gateway.domain.usage import InvocationUsage
from valor.runtime_gateway.infrastructure.models import InvocationRow

TENANT_FOREIGN_KEY = "fk_invocations_tenant_id_tenants"
AGENT_FOREIGN_KEY = "fk_invocations_agent_id_agents"
MODEL_FOREIGN_KEY = "fk_invocations_model_id_models"


class SqlAlchemyInvocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, invocation: Invocation) -> None:
        cost = invocation.estimated_cost
        self._session.add(
            InvocationRow(
                id=invocation.id.value,
                tenant_id=invocation.tenant_id.value,
                agent_id=invocation.agent_id.value,
                model_id=invocation.model_id.value,
                status=invocation.status.value,
                input_text=invocation.input_text,
                output_text=invocation.output_text,
                started_at=invocation.started_at,
                completed_at=invocation.completed_at,
                policy_decision_id=invocation.policy_decision_id.value,
                runtime_principal_id=invocation.runtime_principal_id,
                duration_ms=invocation.duration_ms,
                input_units=invocation.usage.input_units if invocation.usage else None,
                output_units=invocation.usage.output_units if invocation.usage else None,
                total_units=invocation.usage.total_units if invocation.usage else None,
                provider_response_id=invocation.provider_response_id,
                usage_consumed_units=invocation.usage_consumed_units,
                usage_limit_units=invocation.usage_limit_units,
                usage_allowance_units=invocation.usage_allowance_units,
                usage_window_start=invocation.usage_window_start,
                usage_window_end=invocation.usage_window_end,
                cost_currency=cost.currency if cost else None,
                cost_input=cost.input_cost if cost else None,
                cost_output=cost.output_cost if cost else None,
                cost_total=cost.total_cost if cost else None,
                pricing_version=cost.pricing_version if cost else None,
                pricing_basis_units=cost.pricing_basis_units if cost else None,
                pricing_input_rate=cost.pricing_input_rate if cost else None,
                pricing_output_rate=cost.pricing_output_rate if cost else None,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as error:
            if isinstance(error.orig, ForeignKeyViolation):
                constraint = error.orig.diag.constraint_name
                if constraint == TENANT_FOREIGN_KEY:
                    raise TenantNotAvailable(invocation.tenant_id) from error
                if constraint == AGENT_FOREIGN_KEY:
                    raise AgentNotAvailable(invocation.agent_id) from error
                if constraint == MODEL_FOREIGN_KEY:
                    raise ModelNotAvailable(invocation.model_id) from error
            raise

    async def get(self, invocation_id: InvocationId) -> Invocation | None:
        row = await self._session.scalar(
            select(InvocationRow).where(InvocationRow.id == invocation_id.value)
        )
        if row is None:
            return None
        if row.policy_decision_id is None or row.runtime_principal_id is None:
            return None
        return Invocation(
            InvocationId(row.id),
            TenantId(row.tenant_id),
            AgentId(row.agent_id),
            ModelId(row.model_id),
            InvocationStatus(row.status),
            row.input_text,
            row.output_text,
            row.started_at,
            row.completed_at,
            PolicyDecisionId(row.policy_decision_id),
            row.runtime_principal_id,
            row.duration_ms,
            _usage_from_row(row),
            row.provider_response_id,
            row.usage_consumed_units,
            row.usage_limit_units,
            row.usage_allowance_units,
            row.usage_window_start,
            row.usage_window_end,
            _cost_from_row(row),
        )


def _usage_from_row(row: InvocationRow) -> InvocationUsage | None:
    if row.input_units is None and row.output_units is None and row.total_units is None:
        return None
    return InvocationUsage(row.input_units, row.output_units, row.total_units)


def _cost_from_row(row: InvocationRow) -> InvocationCost | None:
    if row.cost_currency is None:
        return None
    if (
        row.cost_input is None
        or row.cost_output is None
        or row.cost_total is None
        or row.pricing_version is None
        or row.pricing_basis_units is None
        or row.pricing_input_rate is None
        or row.pricing_output_rate is None
    ):
        raise ValueError("Persisted Invocation cost snapshot is incomplete.")
    return InvocationCost(
        row.cost_currency,
        row.cost_input,
        row.cost_output,
        row.cost_total,
        row.pricing_version,
        row.pricing_basis_units,
        row.pricing_input_rate,
        row.pricing_output_rate,
    )
