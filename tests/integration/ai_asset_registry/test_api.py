from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.integration.management_helpers import grant_management_scopes


def create_tenant(client: TestClient, name: str) -> UUID:
    response = client.post("/api/v1/tenants", json={"name": name})
    assert response.status_code == 201
    tenant_id = UUID(response.json()["id"])
    grant_management_scopes(client, {tenant_id})
    return tenant_id


def assert_problem(response_status: int, content_type: str, body: dict[str, object]) -> None:
    assert body.keys() >= {"type", "title", "status", "detail", "instance"}
    assert body["status"] == response_status
    assert content_type.startswith("application/problem+json")


@pytest.mark.integration
def test_register_then_get_agent_for_created_tenant(agent_postgres_client: TestClient) -> None:
    tenant_id = create_tenant(agent_postgres_client, "Acme")
    created = agent_postgres_client.post(
        "/api/v1/agents",
        json={"tenant_id": str(tenant_id), "name": " Support  Agent "},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["tenant_id"] == str(tenant_id)
    assert body["name"] == "Support Agent"
    assert created.headers["location"] == f"/api/v1/agents/{body['id']}"

    retrieved = agent_postgres_client.get(f"/api/v1/agents/{body['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json() == body


@pytest.mark.integration
def test_unknown_owning_tenant_returns_not_found(agent_postgres_client: TestClient) -> None:
    response = agent_postgres_client.post(
        "/api/v1/agents",
        json={"tenant_id": str(uuid4()), "name": "Support Agent"},
    )
    assert response.status_code == 404
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Owning Tenant Not Found"


@pytest.mark.integration
def test_duplicate_agent_name_within_tenant_returns_conflict(
    agent_postgres_client: TestClient,
) -> None:
    tenant_id = create_tenant(agent_postgres_client, "Acme")
    first = {"tenant_id": str(tenant_id), "name": "Support Agent"}
    assert agent_postgres_client.post("/api/v1/agents", json=first).status_code == 201
    duplicate = agent_postgres_client.post(
        "/api/v1/agents",
        json={"tenant_id": str(tenant_id), "name": " support   AGENT "},
    )
    assert duplicate.status_code == 409
    assert_problem(duplicate.status_code, duplicate.headers["content-type"], duplicate.json())
    assert duplicate.json()["title"] == "Agent Name Already Exists"


@pytest.mark.integration
def test_same_agent_name_for_different_tenants_is_allowed(
    agent_postgres_client: TestClient,
) -> None:
    first_tenant = create_tenant(agent_postgres_client, "Acme")
    second_tenant = create_tenant(agent_postgres_client, "Globex")
    for tenant_id in (first_tenant, second_tenant):
        response = agent_postgres_client.post(
            "/api/v1/agents",
            json={"tenant_id": str(tenant_id), "name": "Support Agent"},
        )
        assert response.status_code == 201


@pytest.mark.integration
def test_missing_agent_returns_not_found(agent_postgres_client: TestClient) -> None:
    response = agent_postgres_client.get(f"/api/v1/agents/{uuid4()}")
    assert response.status_code == 404
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Agent Not Found"


@pytest.mark.integration
def test_invalid_agent_input_returns_validation_problem(agent_postgres_client: TestClient) -> None:
    response = agent_postgres_client.post(
        "/api/v1/agents",
        json={"tenant_id": "not-a-uuid", "name": ""},
    )
    assert response.status_code == 422
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Request Validation Failed"
