from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.integration.management_helpers import grant_management_scopes, set_management_scopes
from valor.policy_risk.application.set_permission import (
    SetAgentModelPermissionCommand,
    SetAgentModelPermissionHandler,
)
from valor.policy_risk.domain.identity import AgentId, ModelId, TenantId
from valor.policy_risk.domain.policy import PolicyEffect
from valor.policy_risk.infrastructure.admission import PostgresPolicyAdmission
from valor.policy_risk.infrastructure.unit_of_work import SqlAlchemyPolicyUnitOfWork


def _resources(client: TestClient, suffix: str) -> tuple[UUID, UUID, UUID]:
    tenant_id = UUID(client.post("/api/v1/tenants", json={"name": f"Audit {suffix}"}).json()["id"])
    grant_management_scopes(client, {tenant_id})
    agent_id = UUID(
        client.post(
            "/api/v1/agents", json={"tenant_id": str(tenant_id), "name": f"Agent {suffix}"}
        ).json()["id"]
    )
    model_id = UUID(
        client.post(
            "/api/v1/models",
            json={
                "tenant_id": str(tenant_id),
                "name": f"Model {suffix}",
                "provider": "openai",
                "provider_model_reference": f"gpt-{suffix}",
            },
        ).json()["id"]
    )
    return tenant_id, agent_id, model_id


def _put(client: TestClient, tenant: UUID, agent: UUID, model: UUID, effect: str) -> dict[str, str]:
    response = client.put(
        "/api/v1/policies/agent-model-permissions",
        json={
            "tenant_id": str(tenant),
            "agent_id": str(agent),
            "model_id": str(model),
            "effect": effect,
        },
    )
    assert response.status_code == 200
    return cast(dict[str, str], response.json())


def _read(client: TestClient, tenant: UUID) -> list[dict[str, object]]:
    now = datetime.now(UTC)
    response = client.get(
        f"/api/v1/tenants/{tenant}/audit-records",
        params={
            "start": (now - timedelta(days=1)).isoformat(),
            "end": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 200
    return cast(list[dict[str, object]], response.json())


def test_permission_create_update_and_noop_append_fingerprints(
    runtime_client: TestClient,
) -> None:
    tenant, agent, model = _resources(runtime_client, "fingerprints")
    permission = _put(runtime_client, tenant, agent, model, "deny")
    _put(runtime_client, tenant, agent, model, "allow")
    _put(runtime_client, tenant, agent, model, "allow")

    records = _read(runtime_client, tenant)
    assert len(records) == 3
    newest, updated, created = records
    assert created["before_fingerprint"] is None
    assert created["after_fingerprint"] != updated["after_fingerprint"]
    assert updated["before_fingerprint"] == created["after_fingerprint"]
    assert newest["before_fingerprint"] == newest["after_fingerprint"]
    app = cast(FastAPI, runtime_client.app)
    assert newest["principal_id"] == str(app.state.test_management_principal_id)
    assert newest["resource_id"] == permission["id"]
    assert "token" not in str(records).lower()


def test_audit_read_is_tenant_isolated_and_time_bounded(runtime_client: TestClient) -> None:
    tenant_a, agent_a, model_a = _resources(runtime_client, "tenant-a")
    tenant_b, agent_b, model_b = _resources(runtime_client, "tenant-b")
    _put(runtime_client, tenant_a, agent_a, model_a, "allow")
    _put(runtime_client, tenant_b, agent_b, model_b, "deny")
    set_management_scopes(runtime_client, {tenant_a})

    records = _read(runtime_client, tenant_a)
    assert len(records) == 1
    assert records[0]["tenant_id"] == str(tenant_a)
    now = datetime.now(UTC)
    denied = runtime_client.get(
        f"/api/v1/tenants/{tenant_b}/audit-records",
        params={
            "start": (now - timedelta(days=1)).isoformat(),
            "end": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert denied.status_code == 404


def test_audit_read_requires_management_authentication(
    unauthenticated_runtime_client: TestClient,
) -> None:
    tenant = UUID("11111111-1111-4111-8111-111111111111")
    now = datetime.now(UTC)
    response = unauthenticated_runtime_client.get(
        f"/api/v1/tenants/{tenant}/audit-records",
        params={"start": now.isoformat(), "end": (now + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 401


class _FailingAuditRepository:
    async def append(self, record: object) -> None:
        del record
        raise RuntimeError("simulated audit persistence failure")


class _AuditFailingPolicyUnitOfWork(SqlAlchemyPolicyUnitOfWork):
    @property
    def audits(self) -> _FailingAuditRepository:
        return _FailingAuditRepository()


@pytest.mark.asyncio
async def test_audit_append_failure_rolls_back_permission(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant, agent, model = _resources(runtime_client, "atomic-rollback")
    engine = create_async_engine(runtime_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    admission = PostgresPolicyAdmission(sessions)
    uow = _AuditFailingPolicyUnitOfWork(sessions)

    with pytest.raises(RuntimeError, match="simulated audit persistence failure"):
        await SetAgentModelPermissionHandler(uow, admission, admission, admission)(
            SetAgentModelPermissionCommand(
                TenantId(tenant), AgentId(agent), ModelId(model), PolicyEffect.ALLOW, "operator"
            )
        )
    async with SqlAlchemyPolicyUnitOfWork(sessions) as verification:
        assert (
            await verification.permissions.get_effective(
                TenantId(tenant), AgentId(agent), ModelId(model)
            )
            is None
        )
    await engine.dispose()
