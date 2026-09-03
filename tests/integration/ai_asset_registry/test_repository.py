from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from valor.ai_asset_registry.application.errors import (
    AgentNameAlreadyExists,
    OwningTenantNotFound,
)
from valor.ai_asset_registry.domain.agent import Agent, AgentId, OwningTenantId
from valor.ai_asset_registry.infrastructure.tenant_existence import PostgresTenantExistence
from valor.ai_asset_registry.infrastructure.unit_of_work import SqlAlchemyAgentUnitOfWork
from valor.identity_tenancy.domain.tenant import Tenant, TenantId
from valor.identity_tenancy.infrastructure.unit_of_work import SqlAlchemyTenantUnitOfWork

TENANT_UUID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_TENANT_UUID = UUID("22222222-2222-4222-8222-222222222222")
AGENT_ID = AgentId(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
OTHER_AGENT_ID = AgentId(UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"))
CREATED_AT = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)


def sessions_for(
    database_url: str,
) -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def persist_tenant(
    sessions: async_sessionmaker[AsyncSession], tenant_id: UUID, name: str
) -> None:
    tenant = Tenant.create(TenantId(tenant_id), name, CREATED_AT)
    async with SqlAlchemyTenantUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.tenants.add(tenant)
        await unit_of_work.commit()


def agent(agent_id: AgentId, tenant_id: UUID, name: str) -> Agent:
    return Agent.register(agent_id, OwningTenantId(tenant_id), name, CREATED_AT)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_persists_and_reconstitutes_with_tenant_ownership(
    agent_database_url: str,
) -> None:
    sessions, engine = sessions_for(agent_database_url)
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    expected = agent(AGENT_ID, TENANT_UUID, "Support Agent")
    async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.agents.add(expected)
        await unit_of_work.commit()
    async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
        restored = await unit_of_work.agents.get(AGENT_ID)
    assert restored == expected
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_same_normalized_name_is_unique_within_tenant(
    agent_database_url: str,
) -> None:
    sessions, engine = sessions_for(agent_database_url)
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.agents.add(agent(AGENT_ID, TENANT_UUID, "Support Agent"))
        await unit_of_work.commit()
    with pytest.raises(AgentNameAlreadyExists):
        async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
            await unit_of_work.agents.add(agent(OTHER_AGENT_ID, TENANT_UUID, " support  AGENT "))
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_same_normalized_name_is_allowed_for_different_tenants(
    agent_database_url: str,
) -> None:
    sessions, engine = sessions_for(agent_database_url)
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    await persist_tenant(sessions, OTHER_TENANT_UUID, "Globex")
    async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.agents.add(agent(AGENT_ID, TENANT_UUID, "Support Agent"))
        await unit_of_work.commit()
    async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.agents.add(agent(OTHER_AGENT_ID, OTHER_TENANT_UUID, "support agent"))
        await unit_of_work.commit()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_foreign_key_failure_maps_to_unknown_owning_tenant(
    agent_database_url: str,
) -> None:
    sessions, engine = sessions_for(agent_database_url)
    with pytest.raises(OwningTenantNotFound):
        async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
            await unit_of_work.agents.add(agent(AGENT_ID, TENANT_UUID, "Support Agent"))
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_uow_exit_without_commit_rolls_back(agent_database_url: str) -> None:
    sessions, engine = sessions_for(agent_database_url)
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.agents.add(agent(AGENT_ID, TENANT_UUID, "Support Agent"))
    async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
        assert await unit_of_work.agents.get(AGENT_ID) is None
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tenant_existence_adapter_reads_only_identity_contract(
    agent_database_url: str,
) -> None:
    sessions, engine = sessions_for(agent_database_url)
    adapter = PostgresTenantExistence(sessions)
    assert await adapter.exists(OwningTenantId(TENANT_UUID)) is False
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    assert await adapter.exists(OwningTenantId(TENANT_UUID)) is True
    await engine.dispose()
