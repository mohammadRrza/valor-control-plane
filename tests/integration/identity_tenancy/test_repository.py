from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from valor.identity_tenancy.application.errors import TenantNameAlreadyExists
from valor.identity_tenancy.domain.tenant import Tenant, TenantId
from valor.identity_tenancy.infrastructure.unit_of_work import SqlAlchemyTenantUnitOfWork

TENANT_ID = TenantId(UUID("11111111-1111-4111-8111-111111111111"))
OTHER_TENANT_ID = TenantId(UUID("22222222-2222-4222-8222-222222222222"))
CREATED_AT = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


def session_factory(database_url: str) -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False), engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_persists_and_reconstitutes_tenant(tenant_database_url: str) -> None:
    sessions, engine = session_factory(tenant_database_url)
    tenant = Tenant.create(TENANT_ID, "Acme Research", CREATED_AT)
    async with SqlAlchemyTenantUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.tenants.add(tenant)
        await unit_of_work.commit()
    async with SqlAlchemyTenantUnitOfWork(sessions) as unit_of_work:
        restored = await unit_of_work.tenants.get(TENANT_ID)
    assert restored == tenant
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_maps_normalized_name_conflict(tenant_database_url: str) -> None:
    sessions, engine = session_factory(tenant_database_url)
    async with SqlAlchemyTenantUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.tenants.add(Tenant.create(TENANT_ID, "Acme Research", CREATED_AT))
        await unit_of_work.commit()
    with pytest.raises(TenantNameAlreadyExists):
        async with SqlAlchemyTenantUnitOfWork(sessions) as unit_of_work:
            await unit_of_work.tenants.add(
                Tenant.create(OTHER_TENANT_ID, " acme   RESEARCH ", CREATED_AT)
            )
            await unit_of_work.commit()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_uow_exit_without_commit_rolls_back_tenant(tenant_database_url: str) -> None:
    sessions, engine = session_factory(tenant_database_url)
    async with SqlAlchemyTenantUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.tenants.add(Tenant.create(TENANT_ID, "Acme", CREATED_AT))
    async with SqlAlchemyTenantUnitOfWork(sessions) as unit_of_work:
        assert await unit_of_work.tenants.get(TENANT_ID) is None
    await engine.dispose()
