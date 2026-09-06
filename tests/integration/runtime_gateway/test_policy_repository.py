from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.integration.management_helpers import grant_management_scopes
from valor.policy_risk.application.errors import PolicyAgentNotAvailable
from valor.policy_risk.domain.identity import AgentId, ModelId, PermissionId, TenantId
from valor.policy_risk.domain.policy import AgentModelPermission, PolicyEffect
from valor.policy_risk.infrastructure.unit_of_work import SqlAlchemyPolicyUnitOfWork

NOW = datetime(2026, 3, 4, 5, 6, tzinfo=UTC)


def create_references(client: TestClient) -> tuple[UUID, UUID, UUID]:
    tenant = client.post("/api/v1/tenants", json={"name": "Policy Repo Tenant"}).json()["id"]
    tenant_id = UUID(tenant)
    grant_management_scopes(client, {tenant_id})
    agent = client.post(
        "/api/v1/agents", json={"tenant_id": tenant, "name": "Policy Repo Agent"}
    ).json()["id"]
    model = client.post(
        "/api/v1/models",
        json={
            "tenant_id": tenant,
            "name": "Policy Repo Model",
            "provider": "openai",
            "provider_model_reference": "gpt-test",
        },
    ).json()["id"]
    return tenant_id, UUID(agent), UUID(model)


def permission(
    permission_id: UUID,
    tenant_id: UUID,
    agent_id: UUID,
    model_id: UUID,
    effect: PolicyEffect,
    at: datetime = NOW,
) -> AgentModelPermission:
    return AgentModelPermission(
        PermissionId(permission_id),
        TenantId(tenant_id),
        AgentId(agent_id),
        ModelId(model_id),
        effect,
        at,
        at,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_atomic_upsert_preserves_permission_identity_and_creation(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant_id, agent_id, model_id = create_references(runtime_client)
    engine = create_async_engine(runtime_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    first_id = UUID("11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    second_id = UUID("22222222-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    async with SqlAlchemyPolicyUnitOfWork(sessions) as uow:
        first = await uow.permissions.set(
            permission(first_id, tenant_id, agent_id, model_id, PolicyEffect.ALLOW)
        )
        await uow.commit()
    async with SqlAlchemyPolicyUnitOfWork(sessions) as uow:
        updated = await uow.permissions.set(
            permission(
                second_id,
                tenant_id,
                agent_id,
                model_id,
                PolicyEffect.DENY,
                NOW + timedelta(seconds=1),
            )
        )
        await uow.commit()
    assert updated.id == first.id
    assert updated.created_at == first.created_at
    assert updated.effect is PolicyEffect.DENY
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permission_foreign_key_violation_is_translated(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant_id, _, model_id = create_references(runtime_client)
    engine = create_async_engine(runtime_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    with pytest.raises(PolicyAgentNotAvailable):
        async with SqlAlchemyPolicyUnitOfWork(sessions) as uow:
            await uow.permissions.set(
                permission(
                    UUID("11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                    tenant_id,
                    UUID("99999999-9999-4999-8999-999999999999"),
                    model_id,
                    PolicyEffect.ALLOW,
                )
            )
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_permission_uow_exit_without_commit_rolls_back(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant_id, agent_id, model_id = create_references(runtime_client)
    engine = create_async_engine(runtime_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    expected = permission(
        UUID("11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        tenant_id,
        agent_id,
        model_id,
        PolicyEffect.ALLOW,
    )
    async with SqlAlchemyPolicyUnitOfWork(sessions) as uow:
        await uow.permissions.set(expected)
    async with SqlAlchemyPolicyUnitOfWork(sessions) as uow:
        assert await uow.permissions.get(expected.id) is None
    await engine.dispose()
