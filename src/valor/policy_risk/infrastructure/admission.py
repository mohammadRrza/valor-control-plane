from sqlalchemy import Uuid, column, select, table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.policy_risk.application.ports import PolicyAgentIdentity, PolicyModelIdentity
from valor.policy_risk.domain.identity import AgentId, ModelId, TenantId

tenants = table("tenants", column("id", Uuid()))
agents = table("agents", column("id", Uuid()), column("tenant_id", Uuid()))
models = table("models", column("id", Uuid()), column("tenant_id", Uuid()))


class PostgresPolicyAdmission:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def tenant_exists(self, tenant_id: TenantId) -> bool:
        async with self._sessions() as session:
            return (
                await session.scalar(select(tenants.c.id).where(tenants.c.id == tenant_id.value))
                is not None
            )

    async def get_agent(self, agent_id: AgentId) -> PolicyAgentIdentity | None:
        async with self._sessions() as session:
            row = (
                await session.execute(select(agents).where(agents.c.id == agent_id.value))
            ).one_or_none()
        return (
            None if row is None else PolicyAgentIdentity(AgentId(row.id), TenantId(row.tenant_id))
        )

    async def get_model(self, model_id: ModelId) -> PolicyModelIdentity | None:
        async with self._sessions() as session:
            row = (
                await session.execute(select(models).where(models.c.id == model_id.value))
            ).one_or_none()
        return (
            None if row is None else PolicyModelIdentity(ModelId(row.id), TenantId(row.tenant_id))
        )
