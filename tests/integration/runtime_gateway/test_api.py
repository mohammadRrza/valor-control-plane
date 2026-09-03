from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.runtime_gateway.conftest import DeterministicRuntimeProvider


def create_tenant(client: TestClient, name: str) -> UUID:
    response = client.post("/api/v1/tenants", json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["id"])


def create_agent(client: TestClient, tenant_id: UUID, name: str) -> UUID:
    response = client.post("/api/v1/agents", json={"tenant_id": str(tenant_id), "name": name})
    assert response.status_code == 201
    return UUID(response.json()["id"])


def create_model(
    client: TestClient,
    tenant_id: UUID,
    name: str,
    *,
    provider: str = "openai",
) -> UUID:
    response = client.post(
        "/api/v1/models",
        json={
            "tenant_id": str(tenant_id),
            "name": name,
            "provider": provider,
            "provider_model_reference": "gpt-test",
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def runtime_references(client: TestClient) -> tuple[UUID, UUID, UUID]:
    tenant_id = create_tenant(client, "Runtime Acme")
    return (
        tenant_id,
        create_agent(client, tenant_id, "Runtime Agent"),
        create_model(client, tenant_id, "Runtime Model"),
    )


def invocation_payload(tenant_id: UUID, agent_id: UUID, model_id: UUID) -> dict[str, str]:
    return {
        "tenant_id": str(tenant_id),
        "agent_id": str(agent_id),
        "model_id": str(model_id),
        "input": "Explain zero trust.",
    }


def set_permission(
    client: TestClient, tenant_id: UUID, agent_id: UUID, model_id: UUID, effect: str
) -> dict[str, object]:
    response = client.put(
        "/api/v1/policies/agent-model-permissions",
        json={
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "model_id": str(model_id),
            "effect": effect,
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def assert_problem(response_status: int, content_type: str, body: dict[str, object]) -> None:
    assert body.keys() >= {"type", "title", "status", "detail", "instance"}
    assert body["status"] == response_status
    assert content_type.startswith("application/problem+json")


@pytest.mark.integration
def test_create_then_get_invocation_with_deterministic_provider(
    runtime_client: TestClient,
    runtime_provider: DeterministicRuntimeProvider,
) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    set_permission(runtime_client, tenant_id, agent_id, model_id, "allow")
    created = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(tenant_id, agent_id, model_id),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "succeeded"
    assert body["output"] == "provider output for Explain zero trust."
    assert body["input"] == "Explain zero trust."
    assert created.headers["location"] == (f"/api/v1/runtime/invocations/{body['invocation_id']}")
    assert runtime_provider.calls == [("gpt-test", "Explain zero trust.")]
    retrieved = runtime_client.get(f"/api/v1/runtime/invocations/{body['invocation_id']}")
    assert retrieved.status_code == 200
    assert retrieved.json() == body
    assert body["policy_decision_id"]


@pytest.mark.integration
def test_permission_put_replaces_effect_and_preserves_identity(runtime_client: TestClient) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    allowed = set_permission(runtime_client, tenant_id, agent_id, model_id, "allow")
    denied = set_permission(runtime_client, tenant_id, agent_id, model_id, "deny")
    assert denied["id"] == allowed["id"]
    assert denied["created_at"] == allowed["created_at"]
    assert denied["effect"] == "deny"
    response = runtime_client.get(f"/api/v1/policies/agent-model-permissions/{allowed['id']}")
    assert response.status_code == 200
    assert response.json() == denied


@pytest.mark.integration
def test_cross_tenant_permission_definition_is_hidden(runtime_client: TestClient) -> None:
    tenant_id, agent_id, _ = runtime_references(runtime_client)
    other_tenant = create_tenant(runtime_client, "Runtime Globex")
    other_model = create_model(runtime_client, other_tenant, "Other Model")
    response = runtime_client.put(
        "/api/v1/policies/agent-model-permissions",
        json={
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "model_id": str(other_model),
            "effect": "allow",
        },
    )
    assert response.status_code == 404
    assert response.json()["title"] == "Policy Resource Not Found"


@pytest.mark.integration
def test_malformed_permission_effect_is_rejected(runtime_client: TestClient) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    response = runtime_client.put(
        "/api/v1/policies/agent-model-permissions",
        json={
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "model_id": str(model_id),
            "effect": "maybe",
        },
    )
    assert response.status_code == 422
    assert response.json()["title"] == "Request Validation Failed"


@pytest.mark.integration
def test_cross_tenant_agent_is_hidden_as_not_found(runtime_client: TestClient) -> None:
    tenant_id, _, model_id = runtime_references(runtime_client)
    other_tenant = create_tenant(runtime_client, "Runtime Globex")
    other_agent = create_agent(runtime_client, other_tenant, "Other Agent")
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(tenant_id, other_agent, model_id),
    )
    assert response.status_code == 404
    assert response.json()["title"] == "Runtime Resource Not Found"


@pytest.mark.integration
def test_cross_tenant_model_is_hidden_as_not_found(runtime_client: TestClient) -> None:
    tenant_id, agent_id, _ = runtime_references(runtime_client)
    other_tenant = create_tenant(runtime_client, "Runtime Globex")
    other_model = create_model(runtime_client, other_tenant, "Other Model")
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(tenant_id, agent_id, other_model),
    )
    assert response.status_code == 404
    assert response.json()["title"] == "Runtime Resource Not Found"


@pytest.mark.integration
@pytest.mark.parametrize("missing", ["tenant", "agent", "model"])
def test_missing_runtime_reference_returns_non_disclosing_not_found(
    runtime_client: TestClient, missing: str
) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    set_permission(runtime_client, tenant_id, agent_id, model_id, "allow")
    values = {"tenant": tenant_id, "agent": agent_id, "model": model_id}
    values[missing] = uuid4()
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(values["tenant"], values["agent"], values["model"]),
    )
    assert response.status_code == 404
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Runtime Resource Not Found"


@pytest.mark.integration
def test_unsupported_registered_provider_returns_problem(runtime_client: TestClient) -> None:
    tenant_id = create_tenant(runtime_client, "Runtime Acme")
    agent_id = create_agent(runtime_client, tenant_id, "Runtime Agent")
    model_id = create_model(runtime_client, tenant_id, "Anthropic Model", provider="anthropic")
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(tenant_id, agent_id, model_id),
    )
    assert response.status_code == 422
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Provider Not Supported for Runtime"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_failure_returns_bad_gateway_and_persists_failed_invocation(
    runtime_client: TestClient,
    runtime_provider: DeterministicRuntimeProvider,
    runtime_database_url: str,
) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    set_permission(runtime_client, tenant_id, agent_id, model_id, "allow")
    runtime_provider.fails = True
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(tenant_id, agent_id, model_id),
    )
    assert response.status_code == 502
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Model Provider Invocation Failed"
    assert "input" not in response.text.lower()

    engine = create_async_engine(runtime_database_url)
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT i.status, i.output_text, i.input_text, d.effect, "
                    "i.policy_decision_id = d.id AS linked "
                    "FROM invocations i JOIN policy_decisions d "
                    "ON d.invocation_id = i.id "
                    "WHERE i.tenant_id = :tenant_id"
                ),
                {"tenant_id": tenant_id},
            )
        ).one()
    assert row.status == "failed"
    assert row.output_text is None
    assert row.input_text == "Explain zero trust."
    assert row.effect == "allow"
    assert row.linked is True
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.asyncio
async def test_default_and_explicit_deny_never_call_provider(
    runtime_client: TestClient,
    runtime_provider: DeterministicRuntimeProvider,
    runtime_database_url: str,
    explicit: bool,
) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    if explicit:
        set_permission(runtime_client, tenant_id, agent_id, model_id, "deny")
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(tenant_id, agent_id, model_id),
    )
    assert response.status_code == 403
    assert response.json()["title"] == "Invocation Denied"
    assert "decision_id" in response.json()
    assert runtime_provider.calls == []
    engine = create_async_engine(runtime_database_url)
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT i.status, i.policy_decision_id = d.id AS linked, "
                    "d.permission_id FROM invocations i JOIN policy_decisions d "
                    "ON d.invocation_id = i.id WHERE i.tenant_id = :tenant_id"
                ),
                {"tenant_id": tenant_id},
            )
        ).one()
    assert row.status == "denied"
    assert row.linked is True
    assert (row.permission_id is not None) is explicit
    await engine.dispose()


@pytest.mark.integration
def test_missing_invocation_returns_not_found(runtime_client: TestClient) -> None:
    response = runtime_client.get(f"/api/v1/runtime/invocations/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["title"] == "Invocation Not Found"


@pytest.mark.integration
def test_invalid_invocation_input_returns_validation_problem(runtime_client: TestClient) -> None:
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json={
            "tenant_id": "not-a-uuid",
            "agent_id": str(uuid4()),
            "model_id": str(uuid4()),
            "input": "",
        },
    )
    assert response.status_code == 422
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Request Validation Failed"
