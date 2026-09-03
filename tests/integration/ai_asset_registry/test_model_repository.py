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
    ModelNameAlreadyExists,
    OwningTenantNotFound,
)
from valor.ai_asset_registry.domain.model import Model, ModelId, Provider
from valor.ai_asset_registry.domain.ownership import OwningTenantId
from valor.ai_asset_registry.infrastructure.model_unit_of_work import SqlAlchemyModelUnitOfWork
from valor.identity_tenancy.domain.tenant import Tenant, TenantId
from valor.identity_tenancy.infrastructure.unit_of_work import SqlAlchemyTenantUnitOfWork

TENANT_UUID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_TENANT_UUID = UUID("22222222-2222-4222-8222-222222222222")
MODEL_ID = ModelId(UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"))
OTHER_MODEL_ID = ModelId(UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"))
CREATED_AT = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)


def sessions_for(database_url: str) -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def persist_tenant(
    sessions: async_sessionmaker[AsyncSession], tenant_id: UUID, name: str
) -> None:
    async with SqlAlchemyTenantUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.tenants.add(Tenant.create(TenantId(tenant_id), name, CREATED_AT))
        await unit_of_work.commit()


def model(model_id: ModelId, tenant_id: UUID, name: str, reference: str = "gpt-5.2") -> Model:
    return Model.register(
        model_id, OwningTenantId(tenant_id), name, Provider.OPENAI, reference, CREATED_AT
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_model_persists_and_reconstitutes_provider_mapping(
    agent_database_url: str,
) -> None:
    sessions, engine = sessions_for(agent_database_url)
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    expected = model(MODEL_ID, TENANT_UUID, "Support Model")
    async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.models.add(expected)
        await unit_of_work.commit()
    async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
        assert await unit_of_work.models.get(MODEL_ID) == expected
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_model_name_is_unique_by_normalized_value_within_tenant(
    agent_database_url: str,
) -> None:
    sessions, engine = sessions_for(agent_database_url)
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.models.add(model(MODEL_ID, TENANT_UUID, "Support Model"))
        await unit_of_work.commit()
    with pytest.raises(ModelNameAlreadyExists):
        async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
            await unit_of_work.models.add(model(OTHER_MODEL_ID, TENANT_UUID, " support  MODEL "))
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_same_name_is_allowed_for_different_tenants(agent_database_url: str) -> None:
    sessions, engine = sessions_for(agent_database_url)
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    await persist_tenant(sessions, OTHER_TENANT_UUID, "Globex")
    async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.models.add(model(MODEL_ID, TENANT_UUID, "Support Model"))
        await unit_of_work.commit()
    async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.models.add(model(OTHER_MODEL_ID, OTHER_TENANT_UUID, "support model"))
        await unit_of_work.commit()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_same_provider_reference_can_have_distinct_governed_names(
    agent_database_url: str,
) -> None:
    sessions, engine = sessions_for(agent_database_url)
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.models.add(model(MODEL_ID, TENANT_UUID, "Support Model"))
        await unit_of_work.models.add(model(OTHER_MODEL_ID, TENANT_UUID, "Review Model"))
        await unit_of_work.commit()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_model_foreign_key_failure_maps_to_unknown_tenant(
    agent_database_url: str,
) -> None:
    sessions, engine = sessions_for(agent_database_url)
    with pytest.raises(OwningTenantNotFound):
        async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
            await unit_of_work.models.add(model(MODEL_ID, TENANT_UUID, "Support Model"))
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_model_uow_exit_without_commit_rolls_back(agent_database_url: str) -> None:
    sessions, engine = sessions_for(agent_database_url)
    await persist_tenant(sessions, TENANT_UUID, "Acme")
    async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.models.add(model(MODEL_ID, TENANT_UUID, "Support Model"))
    async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
        assert await unit_of_work.models.get(MODEL_ID) is None
    await engine.dispose()
