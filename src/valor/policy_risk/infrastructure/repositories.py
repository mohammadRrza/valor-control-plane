from psycopg.errors import ForeignKeyViolation
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from valor.policy_risk.application.errors import (
    PolicyAgentNotAvailable,
    PolicyModelNotAvailable,
    PolicyTenantNotAvailable,
)
from valor.policy_risk.domain.identity import (
    AgentId,
    ModelId,
    PermissionId,
    TenantId,
)
from valor.policy_risk.domain.policy import AgentModelPermission, PolicyDecision, PolicyEffect
from valor.policy_risk.infrastructure.models import AgentModelPermissionRow, PolicyDecisionRow


def permission_from_row(row: AgentModelPermissionRow) -> AgentModelPermission:
    return AgentModelPermission(
        PermissionId(row.id),
        TenantId(row.tenant_id),
        AgentId(row.agent_id),
        ModelId(row.model_id),
        PolicyEffect(row.effect),
        row.created_at,
        row.updated_at,
    )


class SqlAlchemyAgentModelPermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set(self, permission: AgentModelPermission) -> AgentModelPermission:
        statement = (
            insert(AgentModelPermissionRow)
            .values(
                id=permission.id.value,
                tenant_id=permission.tenant_id.value,
                agent_id=permission.agent_id.value,
                model_id=permission.model_id.value,
                effect=permission.effect.value,
                created_at=permission.created_at,
                updated_at=permission.updated_at,
            )
            .on_conflict_do_update(
                constraint="uq_permissions_tenant_agent_model",
                set_={"effect": permission.effect.value, "updated_at": permission.updated_at},
            )
            .returning(AgentModelPermissionRow)
        )
        try:
            row = await self._session.scalar(statement)
            if row is None:
                raise RuntimeError("Permission upsert returned no row")
            return permission_from_row(row)
        except IntegrityError as error:
            self._translate_fk(error, permission)
            raise

    async def get(self, permission_id: PermissionId) -> AgentModelPermission | None:
        row = await self._session.scalar(
            select(AgentModelPermissionRow).where(AgentModelPermissionRow.id == permission_id.value)
        )
        return None if row is None else permission_from_row(row)

    async def get_effective(
        self, tenant_id: TenantId, agent_id: AgentId, model_id: ModelId
    ) -> AgentModelPermission | None:
        row = await self._session.scalar(
            select(AgentModelPermissionRow).where(
                AgentModelPermissionRow.tenant_id == tenant_id.value,
                AgentModelPermissionRow.agent_id == agent_id.value,
                AgentModelPermissionRow.model_id == model_id.value,
            )
        )
        return None if row is None else permission_from_row(row)

    @staticmethod
    def _translate_fk(error: IntegrityError, permission: AgentModelPermission) -> None:
        if not isinstance(error.orig, ForeignKeyViolation):
            return
        constraint = error.orig.diag.constraint_name
        if constraint == "fk_permissions_tenant_id_tenants":
            raise PolicyTenantNotAvailable(permission.tenant_id) from error
        if constraint == "fk_permissions_agent_id_agents":
            raise PolicyAgentNotAvailable(permission.agent_id) from error
        if constraint == "fk_permissions_model_id_models":
            raise PolicyModelNotAvailable(permission.model_id) from error


class SqlAlchemyPolicyDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, decision: PolicyDecision) -> None:
        self._session.add(
            PolicyDecisionRow(
                id=decision.id.value,
                invocation_id=decision.invocation_id.value,
                tenant_id=decision.tenant_id.value,
                agent_id=decision.agent_id.value,
                model_id=decision.model_id.value,
                permission_id=decision.permission_id.value if decision.permission_id else None,
                effect=decision.effect.value,
                decided_at=decision.decided_at,
            )
        )
        await self._session.flush()
