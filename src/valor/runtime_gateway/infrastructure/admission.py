"""Shared-database adapters for narrow Runtime Gateway admission contracts."""

from sqlalchemy import String, Uuid, column, select, table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.runtime_gateway.application.ports import AgentRuntimeIdentity, ModelRuntimeReference
from valor.runtime_gateway.domain.identity import AgentId, ModelId, TenantId

tenant_identity = table("tenants", column("id", Uuid()))
agent_identity = table("agents", column("id", Uuid()), column("tenant_id", Uuid()))
model_runtime_reference = table(
    "models",
    column("id", Uuid()),
    column("tenant_id", Uuid()),
    column("provider", String()),
    column("provider_model_reference", String()),
)


class PostgresRuntimeAdmission:
    """Reads published schema fields without importing owning-context internals."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def exists(self, tenant_id: TenantId) -> bool:
        statement = select(tenant_identity.c.id).where(tenant_identity.c.id == tenant_id.value)
        async with self._session_factory() as session:
            return await session.scalar(statement) is not None

    async def get_agent(self, agent_id: AgentId) -> AgentRuntimeIdentity | None:
        statement = select(agent_identity.c.id, agent_identity.c.tenant_id).where(
            agent_identity.c.id == agent_id.value
        )
        async with self._session_factory() as session:
            row = (await session.execute(statement)).one_or_none()
        if row is None:
            return None
        return AgentRuntimeIdentity(AgentId(row.id), TenantId(row.tenant_id))

    async def get_model(self, model_id: ModelId) -> ModelRuntimeReference | None:
        statement = select(
            model_runtime_reference.c.id,
            model_runtime_reference.c.tenant_id,
            model_runtime_reference.c.provider,
            model_runtime_reference.c.provider_model_reference,
        ).where(model_runtime_reference.c.id == model_id.value)
        async with self._session_factory() as session:
            row = (await session.execute(statement)).one_or_none()
        if row is None:
            return None
        return ModelRuntimeReference(
            ModelId(row.id),
            TenantId(row.tenant_id),
            row.provider,
            row.provider_model_reference,
        )
