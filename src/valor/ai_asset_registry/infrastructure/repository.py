"""SQLAlchemy Agent repository adapter."""

from psycopg.errors import ForeignKeyViolation, UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from valor.ai_asset_registry.application.errors import (
    AgentNameAlreadyExists,
    OwningTenantNotFound,
)
from valor.ai_asset_registry.domain.agent import Agent, AgentId, AgentName
from valor.ai_asset_registry.domain.ownership import OwningTenantId
from valor.ai_asset_registry.infrastructure.models import AgentRow

AGENT_NAME_UNIQUE_CONSTRAINT = "uq_agents_tenant_id_normalized_name"
AGENT_TENANT_FOREIGN_KEY = "fk_agents_tenant_id_tenants"


class SqlAlchemyAgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, agent: Agent) -> None:
        self._session.add(
            AgentRow(
                id=agent.id.value,
                tenant_id=agent.tenant_id.value,
                name=agent.name.value,
                normalized_name=agent.name.normalized,
                created_at=agent.created_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as error:
            if (
                isinstance(error.orig, UniqueViolation)
                and error.orig.diag.constraint_name == AGENT_NAME_UNIQUE_CONSTRAINT
            ):
                raise AgentNameAlreadyExists from error
            if (
                isinstance(error.orig, ForeignKeyViolation)
                and error.orig.diag.constraint_name == AGENT_TENANT_FOREIGN_KEY
            ):
                raise OwningTenantNotFound(agent.tenant_id) from error
            raise

    async def get(self, agent_id: AgentId) -> Agent | None:
        row = await self._session.scalar(select(AgentRow).where(AgentRow.id == agent_id.value))
        if row is None:
            return None
        return Agent(
            id=AgentId(row.id),
            tenant_id=OwningTenantId(row.tenant_id),
            name=AgentName(row.name),
            created_at=row.created_at,
        )
