from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient


def create_tenant(client: TestClient, name: str) -> UUID:
    response = client.post("/api/v1/tenants", json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["id"])


def model_payload(tenant_id: UUID, name: str = "Support Model") -> dict[str, str]:
    return {
        "tenant_id": str(tenant_id),
        "name": name,
        "provider": "openai",
        "provider_model_reference": "gpt-5.2",
    }


def assert_problem(response_status: int, content_type: str, body: dict[str, object]) -> None:
    assert body.keys() >= {"type", "title", "status", "detail", "instance"}
    assert body["status"] == response_status
    assert content_type.startswith("application/problem+json")


@pytest.mark.integration
def test_register_then_get_governed_model(agent_postgres_client: TestClient) -> None:
    tenant_id = create_tenant(agent_postgres_client, "Acme")
    payload = model_payload(tenant_id)
    payload["name"] = " Support  Model "
    payload["provider_model_reference"] = " gpt-5.2 "
    created = agent_postgres_client.post("/api/v1/models", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["tenant_id"] == str(tenant_id)
    assert body["name"] == "Support Model"
    assert body["provider"] == "openai"
    assert body["provider_model_reference"] == "gpt-5.2"
    assert created.headers["location"] == f"/api/v1/models/{body['id']}"
    retrieved = agent_postgres_client.get(f"/api/v1/models/{body['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json() == body


@pytest.mark.integration
def test_duplicate_model_name_within_tenant_returns_conflict(
    agent_postgres_client: TestClient,
) -> None:
    tenant_id = create_tenant(agent_postgres_client, "Acme")
    assert (
        agent_postgres_client.post("/api/v1/models", json=model_payload(tenant_id)).status_code
        == 201
    )
    duplicate = agent_postgres_client.post(
        "/api/v1/models", json=model_payload(tenant_id, " support  MODEL ")
    )
    assert duplicate.status_code == 409
    assert_problem(duplicate.status_code, duplicate.headers["content-type"], duplicate.json())
    assert duplicate.json()["title"] == "Model Name Already Exists"


@pytest.mark.integration
def test_same_model_name_for_different_tenants_is_allowed(
    agent_postgres_client: TestClient,
) -> None:
    for tenant_name in ("Acme", "Globex"):
        tenant_id = create_tenant(agent_postgres_client, tenant_name)
        assert (
            agent_postgres_client.post("/api/v1/models", json=model_payload(tenant_id)).status_code
            == 201
        )


@pytest.mark.integration
def test_unknown_model_tenant_returns_not_found(agent_postgres_client: TestClient) -> None:
    response = agent_postgres_client.post("/api/v1/models", json=model_payload(uuid4()))
    assert response.status_code == 404
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Owning Tenant Not Found"


@pytest.mark.integration
def test_missing_model_returns_not_found(agent_postgres_client: TestClient) -> None:
    response = agent_postgres_client.get(f"/api/v1/models/{uuid4()}")
    assert response.status_code == 404
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Model Not Found"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("field", "value"),
    [("name", ""), ("provider", "unknown"), ("provider_model_reference", "")],
)
def test_invalid_model_input_returns_validation_problem(
    agent_postgres_client: TestClient, field: str, value: str
) -> None:
    payload = model_payload(uuid4())
    payload[field] = value
    response = agent_postgres_client.post("/api/v1/models", json=payload)
    assert response.status_code == 422
    assert_problem(response.status_code, response.headers["content-type"], response.json())
    assert response.json()["title"] == "Request Validation Failed"
