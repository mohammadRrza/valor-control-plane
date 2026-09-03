from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_create_then_get_tenant(postgres_client: TestClient) -> None:
    created = postgres_client.post("/api/v1/tenants", json={"name": " Acme  Research "})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Acme Research"
    assert created.headers["location"] == f"/api/v1/tenants/{body['id']}"

    retrieved = postgres_client.get(f"/api/v1/tenants/{body['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json() == body


@pytest.mark.integration
def test_duplicate_normalized_tenant_name_returns_problem(postgres_client: TestClient) -> None:
    assert (
        postgres_client.post("/api/v1/tenants", json={"name": "Acme Research"}).status_code == 201
    )
    duplicate = postgres_client.post("/api/v1/tenants", json={"name": " acme   RESEARCH "})
    assert duplicate.status_code == 409
    assert duplicate.headers["content-type"].startswith("application/problem+json")
    assert duplicate.json()["title"] == "Tenant Name Already Exists"


@pytest.mark.integration
def test_missing_tenant_returns_problem(postgres_client: TestClient) -> None:
    response = postgres_client.get(f"/api/v1/tenants/{uuid4()}")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Tenant Not Found"


@pytest.mark.integration
def test_invalid_tenant_name_returns_problem(postgres_client: TestClient) -> None:
    response = postgres_client.post("/api/v1/tenants", json={"name": "   "})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Invalid Tenant Name"
