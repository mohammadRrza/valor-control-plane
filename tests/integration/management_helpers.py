from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

BOOTSTRAP_TOKEN = "test-only-management-bootstrap-token-32-bytes"
PEPPER = "test-only-management-pepper-value-32-bytes"


def bootstrap_management(client: TestClient) -> str:
    response = client.post(
        "/api/v1/management/bootstrap",
        headers={"Authorization": f"Bearer {BOOTSTRAP_TOKEN}"},
        json={"display_name": "Integration Manager", "tenant_ids": []},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    token = str(body["credential"]["bearer_token"])
    client.headers["Authorization"] = f"Bearer {token}"
    app = client.app
    assert isinstance(app, FastAPI)
    app.state.test_management_principal_id = UUID(body["principal"]["principal_id"])
    app.state.test_management_tenant_ids = frozenset()
    return token


def set_management_scopes(client: TestClient, tenant_ids: set[UUID] | frozenset[UUID]) -> None:
    app = client.app
    assert isinstance(app, FastAPI)
    principal_id: UUID = app.state.test_management_principal_id
    response = client.put(
        f"/api/v1/management/principals/{principal_id}/tenant-scopes",
        json={"tenant_ids": [str(value) for value in tenant_ids]},
    )
    assert response.status_code == 200, response.text
    app.state.test_management_tenant_ids = frozenset(tenant_ids)


def grant_management_scopes(client: TestClient, tenant_ids: set[UUID]) -> None:
    app = client.app
    assert isinstance(app, FastAPI)
    current: frozenset[UUID] = app.state.test_management_tenant_ids
    set_management_scopes(client, current | tenant_ids)
