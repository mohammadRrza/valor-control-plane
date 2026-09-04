from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.runtime_gateway.conftest import (
    TEST_MANAGEMENT_TOKEN,
    DeterministicRuntimeProvider,
)
from valor.bootstrap.settings import (
    PricingEntrySettings,
    PricingSettings,
    RuntimeAuthenticationSettings,
    RuntimePrincipalSettings,
)
from valor.runtime_gateway.application.errors import UsageLimitUnavailable
from valor.runtime_gateway.infrastructure.pricing import ConfiguredInvocationPricing


class FailingUsageReader:
    async def consumed_total_units(self, **kwargs: object) -> int:
        del kwargs
        raise UsageLimitUnavailable


def runtime_token(agent_id: UUID) -> str:
    return f"test-runtime-credential-{agent_id}"


def configure_runtime_principal(
    client: TestClient,
    tenant_id: UUID,
    agent_id: UUID,
    *,
    principal_id: str | None = None,
    usage_limit: int = 10_000,
    allowance: int = 100,
) -> None:
    app = cast(FastAPI, client.app)
    current = app.state.settings.runtime_auth.principals
    configured = RuntimePrincipalSettings(
        principal_id=principal_id or f"runtime-{agent_id}",
        tenant_id=tenant_id,
        agent_id=agent_id,
        credential=runtime_token(agent_id),
        usage_limit=usage_limit,
        per_invocation_allowance=allowance,
    )
    app.state.settings.runtime_auth = RuntimeAuthenticationSettings(
        principals=(
            *(
                principal
                for principal in current
                if (principal.tenant_id, principal.agent_id) != (tenant_id, agent_id)
            ),
            configured,
        )
    )


def runtime_headers(agent_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {runtime_token(agent_id)}"}


def configure_pricing(
    client: TestClient, *, version: str, input_rate: str, output_rate: str
) -> None:
    settings = PricingSettings(
        entries=(
            PricingEntrySettings(
                provider="openai",
                provider_model_reference="gpt-test",
                pricing_version=version,
                price_basis_units=1_000_000,
                input_price_per_basis=input_rate,
                output_price_per_basis=output_rate,
            ),
        )
    )
    cast(FastAPI, client.app).state.invocation_pricing = ConfiguredInvocationPricing(settings)


def create_tenant(client: TestClient, name: str) -> UUID:
    response = client.post("/api/v1/tenants", json={"name": name})
    assert response.status_code == 201
    tenant_id = UUID(response.json()["id"])
    security = cast(FastAPI, client.app).state.settings.security
    security.management_tenant_ids = security.management_tenant_ids | {tenant_id}
    return tenant_id


def create_agent(client: TestClient, tenant_id: UUID, name: str) -> UUID:
    response = client.post("/api/v1/agents", json={"tenant_id": str(tenant_id), "name": name})
    assert response.status_code == 201
    agent_id = UUID(response.json()["id"])
    configure_runtime_principal(client, tenant_id, agent_id)
    return agent_id


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


def invocation_payload(model_id: UUID) -> dict[str, str]:
    return {
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
@pytest.mark.parametrize("method", ["post", "get"])
def test_runtime_api_rejects_missing_invalid_and_management_credentials(
    unauthenticated_runtime_client: TestClient,
    method: str,
) -> None:
    path = (
        "/api/v1/runtime/invocations"
        if method == "post"
        else f"/api/v1/runtime/invocations/{uuid4()}"
    )
    payload = {"model_id": str(uuid4()), "input": "runtime"} if method == "post" else None
    for authorization in (None, "Bearer invalid-runtime", f"Bearer {TEST_MANAGEMENT_TOKEN}"):
        headers = {} if authorization is None else {"Authorization": authorization}
        response = unauthenticated_runtime_client.request(
            method, path, json=payload, headers=headers
        )
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert_problem(response.status_code, response.headers["content-type"], response.json())
        assert "invalid-runtime" not in response.text
        assert TEST_MANAGEMENT_TOKEN not in response.text


@pytest.mark.integration
def test_runtime_credential_cannot_authenticate_management_api(
    unauthenticated_runtime_client: TestClient,
) -> None:
    agent_id = uuid4()
    configure_runtime_principal(unauthenticated_runtime_client, uuid4(), agent_id)
    response = unauthenticated_runtime_client.post(
        "/api/v1/tenants",
        json={"name": "Runtime credential must fail"},
        headers=runtime_headers(agent_id),
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_runtime_request_schema_has_no_caller_controlled_identity_claims(
    runtime_client: TestClient,
) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json={
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "model_id": str(model_id),
            "input": "attempted identity override",
        },
        headers=runtime_headers(agent_id),
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_runtime_principals_can_only_read_their_own_invocations(
    runtime_client: TestClient,
) -> None:
    tenant_a, agent_a, model_a = runtime_references(runtime_client)
    tenant_b = create_tenant(runtime_client, "Runtime Principal B")
    agent_b = create_agent(runtime_client, tenant_b, "Agent B")
    model_b = create_model(runtime_client, tenant_b, "Model B")
    set_permission(runtime_client, tenant_a, agent_a, model_a, "allow")
    set_permission(runtime_client, tenant_b, agent_b, model_b, "allow")

    invocation_a = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_a),
        headers=runtime_headers(agent_a),
    )
    invocation_b = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_b),
        headers=runtime_headers(agent_b),
    )
    assert invocation_a.status_code == invocation_b.status_code == 201
    invocation_a_id = invocation_a.json()["invocation_id"]
    invocation_b_id = invocation_b.json()["invocation_id"]
    assert invocation_a.json()["runtime_principal_id"] == f"runtime-{agent_a}"
    assert invocation_b.json()["runtime_principal_id"] == f"runtime-{agent_b}"

    assert (
        runtime_client.get(
            f"/api/v1/runtime/invocations/{invocation_a_id}",
            headers=runtime_headers(agent_a),
        ).status_code
        == 200
    )
    assert (
        runtime_client.get(
            f"/api/v1/runtime/invocations/{invocation_b_id}",
            headers=runtime_headers(agent_b),
        ).status_code
        == 200
    )
    assert (
        runtime_client.get(
            f"/api/v1/runtime/invocations/{invocation_b_id}",
            headers=runtime_headers(agent_a),
        ).status_code
        == 404
    )
    assert (
        runtime_client.get(
            f"/api/v1/runtime/invocations/{invocation_a_id}",
            headers=runtime_headers(agent_b),
        ).status_code
        == 404
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tenant_scoped_management_authorization_is_non_disclosing_and_fail_closed(
    runtime_client: TestClient,
    runtime_provider: DeterministicRuntimeProvider,
    runtime_database_url: str,
) -> None:
    tenant_a_response = runtime_client.post("/api/v1/tenants", json={"name": "Scope A"})
    tenant_b_response = runtime_client.post("/api/v1/tenants", json={"name": "Scope B"})
    assert tenant_a_response.status_code == tenant_b_response.status_code == 201
    tenant_a = UUID(tenant_a_response.json()["id"])
    tenant_b = UUID(tenant_b_response.json()["id"])

    security = cast(FastAPI, runtime_client.app).state.settings.security
    security.management_tenant_ids = frozenset({tenant_a, tenant_b})
    agent_a = create_agent(runtime_client, tenant_a, "Agent A")
    model_a = create_model(runtime_client, tenant_a, "Model A")
    agent_b = create_agent(runtime_client, tenant_b, "Agent B")
    model_b = create_model(runtime_client, tenant_b, "Model B")
    audit_agent_b = create_agent(runtime_client, tenant_b, "Audit Agent B")
    audit_model_b = create_model(runtime_client, tenant_b, "Audit Model B")
    denied_permission_b = set_permission(
        runtime_client, tenant_b, audit_agent_b, audit_model_b, "deny"
    )

    security.management_tenant_ids = frozenset({tenant_a})
    assert runtime_client.get(f"/api/v1/tenants/{tenant_a}").status_code == 200
    assert runtime_client.get(f"/api/v1/tenants/{tenant_b}").status_code == 404
    assert runtime_client.get(f"/api/v1/agents/{agent_a}").status_code == 200
    assert runtime_client.get(f"/api/v1/agents/{agent_b}").status_code == 404
    assert runtime_client.get(f"/api/v1/models/{model_a}").status_code == 200
    assert runtime_client.get(f"/api/v1/models/{model_b}").status_code == 404
    assert (
        runtime_client.get(
            f"/api/v1/policies/agent-model-permissions/{denied_permission_b['id']}"
        ).status_code
        == 404
    )

    assert (
        runtime_client.post(
            "/api/v1/agents",
            json={"tenant_id": str(tenant_a), "name": "Another Agent A"},
        ).status_code
        == 201
    )
    assert (
        runtime_client.post(
            "/api/v1/agents",
            json={"tenant_id": str(tenant_b), "name": "Another Agent B"},
        ).status_code
        == 404
    )
    assert (
        runtime_client.post(
            "/api/v1/models",
            json={
                "tenant_id": str(tenant_a),
                "name": "Another Model A",
                "provider": "openai",
                "provider_model_reference": "gpt-test",
            },
        ).status_code
        == 201
    )
    assert (
        runtime_client.post(
            "/api/v1/models",
            json={
                "tenant_id": str(tenant_b),
                "name": "Another Model B",
                "provider": "openai",
                "provider_model_reference": "gpt-test",
            },
        ).status_code
        == 404
    )

    set_permission(runtime_client, tenant_a, agent_a, model_a, "allow")
    unauthorized_allow = runtime_client.put(
        "/api/v1/policies/agent-model-permissions",
        json={
            "tenant_id": str(tenant_b),
            "agent_id": str(agent_b),
            "model_id": str(model_b),
            "effect": "allow",
        },
    )
    assert unauthorized_allow.status_code == 404
    denied_runtime = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_b),
        headers=runtime_headers(agent_b),
    )
    assert denied_runtime.status_code == 403
    assert runtime_provider.calls == []

    engine = create_async_engine(runtime_database_url)
    async with engine.connect() as connection:
        target_permission_count = await connection.scalar(
            text(
                "SELECT count(*) FROM agent_model_permissions "
                "WHERE tenant_id = :tenant_id AND agent_id = :agent_id AND model_id = :model_id"
            ),
            {"tenant_id": tenant_b, "agent_id": agent_b, "model_id": model_b},
        )
        decision_permission_id = await connection.scalar(
            text("SELECT permission_id FROM policy_decisions WHERE id = :decision_id"),
            {"decision_id": UUID(denied_runtime.json()["decision_id"])},
        )
    await engine.dispose()
    assert target_permission_count == 0
    assert decision_permission_id is None


@pytest.mark.integration
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/v1/tenants", {"name": "Anonymous Tenant"}),
        (
            "post",
            "/api/v1/agents",
            {"tenant_id": str(uuid4()), "name": "Anonymous Agent"},
        ),
        (
            "post",
            "/api/v1/models",
            {
                "tenant_id": str(uuid4()),
                "name": "Anonymous Model",
                "provider": "openai",
                "provider_model_reference": "gpt-test",
            },
        ),
        (
            "put",
            "/api/v1/policies/agent-model-permissions",
            {
                "tenant_id": str(uuid4()),
                "agent_id": str(uuid4()),
                "model_id": str(uuid4()),
                "effect": "allow",
            },
        ),
    ],
)
def test_management_mutations_require_authentication(
    unauthenticated_runtime_client: TestClient,
    method: str,
    path: str,
    payload: dict[str, str],
) -> None:
    response = unauthenticated_runtime_client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert_problem(response.status_code, response.headers["content-type"], response.json())


@pytest.mark.integration
def test_management_reads_and_invalid_credentials_are_rejected(
    unauthenticated_runtime_client: TestClient,
) -> None:
    permission_id = uuid4()
    anonymous = unauthenticated_runtime_client.get(
        f"/api/v1/policies/agent-model-permissions/{permission_id}"
    )
    invalid = unauthenticated_runtime_client.get(
        f"/api/v1/policies/agent-model-permissions/{permission_id}",
        headers={"Authorization": "Bearer invalid"},
    )
    assert anonymous.status_code == invalid.status_code == 401
    assert anonymous.json() == invalid.json()
    assert "Bearer invalid" not in invalid.text


@pytest.mark.integration
def test_health_is_public_but_runtime_requires_separate_credential(
    unauthenticated_runtime_client: TestClient,
) -> None:
    assert unauthenticated_runtime_client.get("/health/live").status_code == 200
    runtime = unauthenticated_runtime_client.post(
        "/api/v1/runtime/invocations",
        json={
            "model_id": str(uuid4()),
            "input": "No management credential",
        },
    )
    assert runtime.status_code == 401
    assert runtime.json()["title"] == "Unauthorized"


@pytest.mark.integration
def test_anonymous_policy_mutation_cannot_bypass_default_deny(
    unauthenticated_runtime_client: TestClient,
    runtime_provider: DeterministicRuntimeProvider,
) -> None:
    auth = {"Authorization": f"Bearer {TEST_MANAGEMENT_TOKEN}"}
    tenant_response = unauthenticated_runtime_client.post(
        "/api/v1/tenants", json={"name": "Security Regression"}, headers=auth
    )
    assert tenant_response.status_code == 201
    tenant_id = UUID(tenant_response.json()["id"])
    security = cast(FastAPI, unauthenticated_runtime_client.app).state.settings.security
    security.management_tenant_ids = frozenset({tenant_id})
    agent_response = unauthenticated_runtime_client.post(
        "/api/v1/agents",
        json={"tenant_id": str(tenant_id), "name": "Security Agent"},
        headers=auth,
    )
    model_response = unauthenticated_runtime_client.post(
        "/api/v1/models",
        json={
            "tenant_id": str(tenant_id),
            "name": "Security Model",
            "provider": "openai",
            "provider_model_reference": "gpt-test",
        },
        headers=auth,
    )
    agent_id = UUID(agent_response.json()["id"])
    model_id = UUID(model_response.json()["id"])
    configure_runtime_principal(unauthenticated_runtime_client, tenant_id, agent_id)
    permission_payload = {
        "tenant_id": str(tenant_id),
        "agent_id": str(agent_id),
        "model_id": str(model_id),
        "effect": "allow",
    }

    anonymous_allow = unauthenticated_runtime_client.put(
        "/api/v1/policies/agent-model-permissions", json=permission_payload
    )
    assert anonymous_allow.status_code == 401
    denied = unauthenticated_runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_id),
        headers=runtime_headers(agent_id),
    )
    assert denied.status_code == 403
    assert runtime_provider.calls == []

    authenticated_allow = unauthenticated_runtime_client.put(
        "/api/v1/policies/agent-model-permissions",
        json=permission_payload,
        headers=auth,
    )
    assert authenticated_allow.status_code == 200
    allowed = unauthenticated_runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_id),
        headers=runtime_headers(agent_id),
    )
    assert allowed.status_code == 201
    assert runtime_provider.calls == [("gpt-test", "Explain zero trust.")]


@pytest.mark.integration
def test_create_then_get_invocation_with_deterministic_provider(
    runtime_client: TestClient,
    runtime_provider: DeterministicRuntimeProvider,
) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    set_permission(runtime_client, tenant_id, agent_id, model_id, "allow")
    created = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_id),
        headers=runtime_headers(agent_id),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "succeeded"
    assert body["output"] == "provider output for Explain zero trust."
    assert body["input"] == "Explain zero trust."
    assert isinstance(body["duration_ms"], int) and body["duration_ms"] >= 0
    assert body["usage"] == {
        "input_units": 17,
        "output_units": 9,
        "total_units": 26,
    }
    assert body["provider_response_id"] == "resp_deterministic_123"
    assert body["estimated_cost"] is None
    assert created.headers["location"] == (f"/api/v1/runtime/invocations/{body['invocation_id']}")
    assert runtime_provider.calls == [("gpt-test", "Explain zero trust.")]
    retrieved = runtime_client.get(
        f"/api/v1/runtime/invocations/{body['invocation_id']}",
        headers=runtime_headers(agent_id),
    )
    assert retrieved.status_code == 200
    assert retrieved.json() == body
    assert body["policy_decision_id"]


@pytest.mark.integration
def test_cost_snapshot_is_exact_and_stable_after_pricing_change(
    runtime_client: TestClient,
) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    set_permission(runtime_client, tenant_id, agent_id, model_id, "allow")
    configure_pricing(runtime_client, version="synthetic-v1", input_rate="2", output_rate="8")
    created = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_id),
        headers=runtime_headers(agent_id),
    )
    assert created.status_code == 201
    expected = {
        "currency": "USD",
        "input": "0.000034000000",
        "output": "0.000072000000",
        "total": "0.000106000000",
        "pricing_version": "synthetic-v1",
    }
    assert created.json()["estimated_cost"] == expected

    configure_pricing(runtime_client, version="synthetic-v2", input_rate="20", output_rate="80")
    retrieved = runtime_client.get(
        f"/api/v1/runtime/invocations/{created.json()['invocation_id']}",
        headers=runtime_headers(agent_id),
    )
    assert retrieved.status_code == 200
    assert retrieved.json()["estimated_cost"] == expected


@pytest.mark.integration
def test_missing_provider_usage_keeps_successful_invocation_cost_unavailable(
    runtime_client: TestClient,
    runtime_provider: DeterministicRuntimeProvider,
) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    set_permission(runtime_client, tenant_id, agent_id, model_id, "allow")
    configure_pricing(runtime_client, version="synthetic-v1", input_rate="2", output_rate="8")
    runtime_provider.usage_available = False
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_id),
        headers=runtime_headers(agent_id),
    )
    assert response.status_code == 201
    assert response.json()["usage"] is None
    assert response.json()["estimated_cost"] is None


@pytest.mark.integration
def test_daily_usage_limit_sequence_and_principal_isolation(
    runtime_client: TestClient,
    runtime_provider: DeterministicRuntimeProvider,
) -> None:
    tenant_a, agent_a, model_a = runtime_references(runtime_client)
    configure_runtime_principal(runtime_client, tenant_a, agent_a, usage_limit=300, allowance=100)
    set_permission(runtime_client, tenant_a, agent_a, model_a, "allow")
    runtime_provider.usage_totals = [90, 110, 80]

    for expected_total in (90, 110, 80):
        response = runtime_client.post(
            "/api/v1/runtime/invocations",
            json=invocation_payload(model_a),
            headers=runtime_headers(agent_a),
        )
        assert response.status_code == 201
        assert response.json()["usage"]["total_units"] == expected_total

    limited = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_a),
        headers=runtime_headers(agent_a),
    )
    assert limited.status_code == 429
    assert limited.json()["title"] == "Runtime Usage Limit Reached"
    assert len(runtime_provider.calls) == 3
    limited_id = limited.json()["invocation_id"]
    retrieved = runtime_client.get(
        f"/api/v1/runtime/invocations/{limited_id}", headers=runtime_headers(agent_a)
    )
    assert retrieved.status_code == 200
    evidence = retrieved.json()
    assert evidence["status"] == "limited"
    assert evidence["usage_consumed_units"] == 280
    assert evidence["usage_limit_units"] == 300
    assert evidence["usage_allowance_units"] == 100
    assert evidence["usage"] is None
    assert evidence["provider_response_id"] is None
    assert evidence["estimated_cost"] is None

    tenant_b = create_tenant(runtime_client, "Independent Usage Principal")
    agent_b = create_agent(runtime_client, tenant_b, "Independent Agent")
    model_b = create_model(runtime_client, tenant_b, "Independent Model")
    configure_runtime_principal(runtime_client, tenant_b, agent_b, usage_limit=300, allowance=100)
    set_permission(runtime_client, tenant_b, agent_b, model_b, "allow")
    assert (
        runtime_client.get(
            f"/api/v1/runtime/invocations/{limited_id}", headers=runtime_headers(agent_b)
        ).status_code
        == 404
    )
    allowed_b = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_b),
        headers=runtime_headers(agent_b),
    )
    assert allowed_b.status_code == 201


@pytest.mark.integration
def test_usage_reader_failure_returns_503_without_provider_execution(
    runtime_client: TestClient,
    runtime_provider: DeterministicRuntimeProvider,
) -> None:
    tenant_id, agent_id, model_id = runtime_references(runtime_client)
    set_permission(runtime_client, tenant_id, agent_id, model_id, "allow")
    cast(FastAPI, runtime_client.app).state.runtime_usage_reader = FailingUsageReader()
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_id),
        headers=runtime_headers(agent_id),
    )
    assert response.status_code == 503
    assert response.json()["title"] == "Runtime Usage Check Unavailable"
    assert runtime_provider.calls == []


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
    _, _, model_id = runtime_references(runtime_client)
    other_tenant = create_tenant(runtime_client, "Runtime Globex")
    other_agent = create_agent(runtime_client, other_tenant, "Other Agent")
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(model_id),
        headers=runtime_headers(other_agent),
    )
    assert response.status_code == 404
    assert response.json()["title"] == "Runtime Resource Not Found"


@pytest.mark.integration
def test_cross_tenant_model_is_hidden_as_not_found(runtime_client: TestClient) -> None:
    _, agent_id, _ = runtime_references(runtime_client)
    other_tenant = create_tenant(runtime_client, "Runtime Globex")
    other_model = create_model(runtime_client, other_tenant, "Other Model")
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(other_model),
        headers=runtime_headers(agent_id),
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
    authenticated_agent = agent_id
    requested_model = model_id
    if missing == "tenant":
        authenticated_agent = uuid4()
        configure_runtime_principal(runtime_client, uuid4(), authenticated_agent)
    elif missing == "agent":
        authenticated_agent = uuid4()
        configure_runtime_principal(runtime_client, tenant_id, authenticated_agent)
    else:
        requested_model = uuid4()
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json=invocation_payload(requested_model),
        headers=runtime_headers(authenticated_agent),
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
        json=invocation_payload(model_id),
        headers=runtime_headers(agent_id),
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
        json=invocation_payload(model_id),
        headers=runtime_headers(agent_id),
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
                    "SELECT i.status, i.output_text, i.input_text, i.duration_ms, "
                    "i.input_units, i.output_units, i.total_units, "
                    "i.provider_response_id, i.cost_total, d.effect, "
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
    assert row.duration_ms >= 0
    assert row.input_units is row.output_units is row.total_units is None
    assert row.provider_response_id is None
    assert row.cost_total is None
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
        json=invocation_payload(model_id),
        headers=runtime_headers(agent_id),
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
                    "SELECT i.status, i.duration_ms, i.input_units, i.output_units, "
                    "i.total_units, i.provider_response_id, i.cost_total, "
                    "i.policy_decision_id = d.id AS linked, "
                    "d.permission_id FROM invocations i JOIN policy_decisions d "
                    "ON d.invocation_id = i.id WHERE i.tenant_id = :tenant_id"
                ),
                {"tenant_id": tenant_id},
            )
        ).one()
    assert row.status == "denied"
    assert row.duration_ms >= 0
    assert row.input_units is row.output_units is row.total_units is None
    assert row.provider_response_id is None
    assert row.cost_total is None
    assert row.linked is True
    assert (row.permission_id is not None) is explicit
    await engine.dispose()


@pytest.mark.integration
def test_missing_invocation_returns_not_found(runtime_client: TestClient) -> None:
    _, agent_id, _ = runtime_references(runtime_client)
    response = runtime_client.get(
        f"/api/v1/runtime/invocations/{uuid4()}", headers=runtime_headers(agent_id)
    )
    assert response.status_code == 404
    assert response.json()["title"] == "Invocation Not Found"


@pytest.mark.integration
def test_invalid_invocation_input_returns_validation_problem(runtime_client: TestClient) -> None:
    _, agent_id, model_id = runtime_references(runtime_client)
    response = runtime_client.post(
        "/api/v1/runtime/invocations",
        json={
            "model_id": str(model_id),
            "input": "",
        },
        headers=runtime_headers(agent_id),
    )
    assert response.status_code == 422
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Request Validation Failed"
