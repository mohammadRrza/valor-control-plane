"""PostgreSQL adapter for the narrow tenant-existence contract."""

from sqlalchemy import Uuid, column, select, table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.ai_asset_registry.domain.ownership import OwningTenantId

tenant_identity = table("tenants", column("id", Uuid()))


class PostgresTenantExistence:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def exists(self, tenant_id: OwningTenantId) -> bool:
        statement = select(tenant_identity.c.id).where(tenant_identity.c.id == tenant_id.value)
        async with self._session_factory() as session:
            return await session.scalar(statement) is not None
