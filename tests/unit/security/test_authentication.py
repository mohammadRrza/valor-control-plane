from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from valor.management_identity.application.authentication import AuthenticatedManagementIdentity
from valor.security.application.principal import AuthenticatedPrincipal, PrincipalKind
from valor.security.presentation.authentication import require_management_principal
from valor.security.presentation.errors import install_security_error_handlers

TOKEN = "unit-test-management-token-at-least-32-bytes"
PRINCIPAL_ID = UUID("11111111-1111-4111-8111-111111111111")
CREDENTIAL_ID = UUID("22222222-2222-4222-8222-222222222222")


class Authenticator:
    async def authenticate(self, token: str) -> AuthenticatedManagementIdentity | None:
        if token != TOKEN:
            return None
        return AuthenticatedManagementIdentity(PRINCIPAL_ID, CREDENTIAL_ID, frozenset(), True)


@pytest.fixture
def authentication_client() -> TestClient:
    app = FastAPI()
    app.state.management_authenticator = Authenticator()

    @app.get("/protected")
    async def protected(
        principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    ) -> dict[str, str]:
        return {
            "principal_id": str(principal.principal_id),
            "credential_id": str(principal.credential_id),
            "principal_kind": principal.principal_kind,
        }

    install_security_error_handlers(app)
    return TestClient(app)


def test_valid_token_returns_stable_non_secret_principal(authentication_client: TestClient) -> None:
    response = authentication_client.get("/protected", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json() == {
        "principal_id": str(PRINCIPAL_ID),
        "credential_id": str(CREDENTIAL_ID),
        "principal_kind": PrincipalKind.MANAGEMENT,
    }
    assert TOKEN not in response.text


@pytest.mark.parametrize(
    "authorization", [None, "Basic credentials", "Bearer wrong-token", "Bearer "]
)
def test_missing_malformed_or_invalid_credentials_share_sanitized_failure(
    authentication_client: TestClient, authorization: str | None
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    response = authentication_client.get("/protected", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["detail"] == "Authentication credentials are missing or invalid."
    assert TOKEN not in response.text


def test_principal_representation_never_contains_credential_secret() -> None:
    principal = AuthenticatedPrincipal(
        PRINCIPAL_ID, CREDENTIAL_ID, PrincipalKind.MANAGEMENT, frozenset(), True
    )
    assert TOKEN not in repr(principal)
    assert not hasattr(principal, "token")


def test_nil_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="nil UUIDs"):
        AuthenticatedPrincipal(
            UUID(int=0), CREDENTIAL_ID, PrincipalKind.MANAGEMENT, frozenset(), True
        )
