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
from valor.runtime_gateway.domain.identity import (
    AgentId,
    InvocationId,
    ModelId,
    PolicyDecisionId,
    TenantId,
)
from valor.runtime_gateway.domain.invocation import Invocation, InvocationStatus
from valor.runtime_gateway.infrastructure.models import InvocationRow

TENANT_FOREIGN_KEY = "fk_invocations_tenant_id_tenants"
AGENT_FOREIGN_KEY = "fk_invocations_agent_id_agents"
MODEL_FOREIGN_KEY = "fk_invocations_model_id_models"


class SqlAlchemyInvocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, invocation: Invocation) -> None:
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
        if row.policy_decision_id is None:
            raise RuntimeError("Legacy Invocation has no policy decision link")
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
        )
