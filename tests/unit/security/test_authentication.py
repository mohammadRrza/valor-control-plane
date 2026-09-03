from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from valor.bootstrap.settings import (
    DatabaseSettings,
    RuntimeAuthenticationSettings,
    SecuritySettings,
    Settings,
)
from valor.security.application.principal import AuthenticatedPrincipal, PrincipalKind
from valor.security.presentation.authentication import require_management_principal
from valor.security.presentation.errors import install_security_error_handlers

TOKEN = "unit-test-management-token-at-least-32-bytes"


@pytest.fixture
def authentication_client() -> TestClient:
    app = FastAPI()
    app.state.settings = Settings(
        database=DatabaseSettings(url="postgresql+psycopg://valor:valor@localhost/valor"),
        security=SecuritySettings(
            management_principal_id="stable-operator",
            management_token=TOKEN,
            management_tenant_ids=frozenset(),
        ),
        runtime_auth=RuntimeAuthenticationSettings(principals=()),
    )

    @app.get("/protected")
    def protected(
        principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    ) -> dict[str, str]:
        return {
            "principal_id": principal.principal_id,
            "principal_kind": principal.principal_kind,
        }

    install_security_error_handlers(app)
    return TestClient(app)


def test_valid_token_returns_stable_non_secret_principal(
    authentication_client: TestClient,
) -> None:
    response = authentication_client.get("/protected", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json() == {
        "principal_id": "stable-operator",
        "principal_kind": PrincipalKind.MANAGEMENT,
    }
    assert TOKEN not in response.text


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic credentials", "Bearer wrong-token", "Bearer "],
)
def test_missing_malformed_or_invalid_credentials_share_sanitized_failure(
    authentication_client: TestClient, authorization: str | None
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    response = authentication_client.get("/protected", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
        "detail": "Authentication credentials are missing or invalid.",
        "instance": "/protected",
    }
    assert TOKEN not in response.text


def test_principal_representation_never_contains_credential() -> None:
    principal = AuthenticatedPrincipal("stable-operator", PrincipalKind.MANAGEMENT, frozenset())
    assert TOKEN not in repr(principal)
    assert not hasattr(principal, "token")


def test_principal_identity_cannot_be_empty() -> None:
    with pytest.raises(ValueError, match="principal_id must not be empty"):
        AuthenticatedPrincipal(" ", PrincipalKind.MANAGEMENT, frozenset())
