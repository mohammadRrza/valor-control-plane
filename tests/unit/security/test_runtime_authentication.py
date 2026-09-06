from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from valor.bootstrap.settings import (
    DatabaseSettings,
    RuntimeAuthenticationSettings,
    RuntimePrincipalSettings,
    SecuritySettings,
    Settings,
)
from valor.security.application.runtime_principal import RuntimePrincipal
from valor.security.presentation.errors import install_security_error_handlers
from valor.security.presentation.runtime_authentication import require_runtime_principal

RUNTIME_TOKEN = "unit-runtime-credential-at-least-32-bytes"
TENANT_ID = UUID("11111111-1111-4111-8111-111111111111")
AGENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


@pytest.fixture
def runtime_authentication_client() -> TestClient:
    app = FastAPI()
    app.state.settings = Settings(
        database=DatabaseSettings(url="postgresql+psycopg://valor:valor@localhost/valor"),
        security=SecuritySettings(
            management_bootstrap_token="unit-management-bootstrap-at-least-32-bytes",
            management_credential_pepper="unit-management-pepper-at-least-32-bytes",
        ),
        runtime_auth=RuntimeAuthenticationSettings(
            principals=(
                RuntimePrincipalSettings(
                    principal_id="runtime-agent-a",
                    tenant_id=TENANT_ID,
                    agent_id=AGENT_ID,
                    credential=RUNTIME_TOKEN,
                    usage_limit=1000,
                    per_invocation_allowance=100,
                ),
            )
        ),
    )

    @app.get("/runtime")
    def runtime(
        principal: Annotated[RuntimePrincipal, Depends(require_runtime_principal)],
    ) -> dict[str, str | int]:
        return {
            "principal_id": principal.principal_id,
            "tenant_id": str(principal.tenant_id),
            "agent_id": str(principal.agent_id),
            "usage_limit": principal.usage_limit,
            "per_invocation_allowance": principal.per_invocation_allowance,
        }

    install_security_error_handlers(app)
    return TestClient(app)


def test_runtime_credential_resolves_bound_non_secret_identity(
    runtime_authentication_client: TestClient,
) -> None:
    response = runtime_authentication_client.get(
        "/runtime", headers={"Authorization": f"Bearer {RUNTIME_TOKEN}"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "principal_id": "runtime-agent-a",
        "tenant_id": str(TENANT_ID),
        "agent_id": str(AGENT_ID),
        "usage_limit": 1000,
        "per_invocation_allowance": 100,
    }
    assert RUNTIME_TOKEN not in response.text


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic credentials", "Bearer wrong", "Bearer "],
)
def test_runtime_authentication_failures_are_sanitized(
    runtime_authentication_client: TestClient,
    authorization: str | None,
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    response = runtime_authentication_client.get("/runtime", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert RUNTIME_TOKEN not in response.text


def test_runtime_principal_contains_no_credential() -> None:
    principal = RuntimePrincipal("runtime-agent-a", TENANT_ID, AGENT_ID, 1000, 100)
    assert not hasattr(principal, "credential")
    assert RUNTIME_TOKEN not in repr(principal)


def test_runtime_principal_identity_cannot_be_empty() -> None:
    with pytest.raises(ValueError, match="principal_id must not be empty"):
        RuntimePrincipal(" ", TENANT_ID, AGENT_ID, 1000, 100)
