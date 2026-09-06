from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from valor.management_identity.application.authentication import ManagementAuthenticator
from valor.management_identity.application.ports import ManagementIdentityUnitOfWork
from valor.management_identity.application.secrets import (
    generate_bearer_token,
    parse_bearer_token,
    secret_verifier,
)
from valor.management_identity.domain.models import ManagementCredential, ManagementPrincipal

NOW = datetime(2026, 9, 6, tzinfo=UTC)
PRINCIPAL_ID = UUID("11111111-1111-4111-8111-111111111111")
CREDENTIAL_ID = UUID("22222222-2222-4222-8222-222222222222")
TENANT_ID = UUID("33333333-3333-4333-8333-333333333333")
PEPPER = "unit-test-pepper-at-least-32-bytes-long"


def principal(*, disabled: bool = False) -> ManagementPrincipal:
    return ManagementPrincipal(
        PRINCIPAL_ID,
        "  Alice   Operations ",
        True,
        frozenset({TENANT_ID}),
        NOW,
        NOW if disabled else None,
    )


def credential(
    secret: str, *, revoked: bool = False, expires_at: datetime | None = None
) -> ManagementCredential:
    return ManagementCredential(
        CREDENTIAL_ID,
        PRINCIPAL_ID,
        secret_verifier(secret, PEPPER),
        " deployment  one ",
        NOW,
        expires_at,
        NOW if revoked else None,
    )


def test_principal_normalizes_name_allows_empty_scope_and_disables_terminally() -> None:
    value = principal()
    assert value.display_name == "Alice Operations"
    assert value.is_active
    assert (
        ManagementPrincipal(PRINCIPAL_ID, "Automation", False, frozenset(), NOW).tenant_ids
        == frozenset()
    )
    disabled = value.disable(NOW + timedelta(seconds=1))
    assert not disabled.is_active
    with pytest.raises(ValueError, match="already disabled"):
        disabled.disable(NOW + timedelta(seconds=2))


def test_credential_expiry_boundary_and_permanent_revocation() -> None:
    expires = NOW + timedelta(hours=1)
    value = credential("secret", expires_at=expires)
    assert value.label == "deployment one"
    assert value.is_usable_at(expires - timedelta(microseconds=1))
    assert not value.is_usable_at(expires)
    revoked = value.revoke(NOW + timedelta(minutes=1))
    assert not revoked.is_usable_at(NOW + timedelta(minutes=2))
    with pytest.raises(ValueError, match="already revoked"):
        revoked.revoke(NOW + timedelta(minutes=3))


def test_generated_bearer_has_public_id_and_high_entropy_secret() -> None:
    token, secret = generate_bearer_token(CREDENTIAL_ID)
    assert len(secret) >= 43
    assert parse_bearer_token(token) == (CREDENTIAL_ID, secret)
    verifier = secret_verifier(secret, PEPPER)
    assert verifier != secret
    assert token != verifier
    assert len(verifier) == 64
    assert parse_bearer_token("malformed") is None


class PrincipalRepository:
    def __init__(self, value: ManagementPrincipal | None) -> None:
        self.value = value

    async def get(self, principal_id: UUID) -> ManagementPrincipal | None:
        assert principal_id == PRINCIPAL_ID
        return self.value


class CredentialRepository:
    def __init__(self, value: ManagementCredential | None) -> None:
        self.value = value

    async def get(self, credential_id: UUID) -> ManagementCredential | None:
        assert credential_id == CREDENTIAL_ID
        return self.value


class AuthenticationUow:
    def __init__(
        self,
        principal_value: ManagementPrincipal | None,
        credential_value: ManagementCredential | None,
    ) -> None:
        self.principals = PrincipalRepository(principal_value)
        self.credentials = CredentialRepository(credential_value)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass


class Factory:
    def __init__(
        self,
        principal_value: ManagementPrincipal | None,
        credential_value: ManagementCredential | None,
    ) -> None:
        self.principal = principal_value
        self.credential = credential_value

    def __call__(self) -> ManagementIdentityUnitOfWork:
        return cast(
            ManagementIdentityUnitOfWork,
            AuthenticationUow(self.principal, self.credential),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unknown", "wrong", "revoked", "expired", "disabled"])
async def test_authentication_failures_are_indistinguishable(failure: str) -> None:
    token, secret = generate_bearer_token(CREDENTIAL_ID)
    principal_value: ManagementPrincipal | None = principal(disabled=failure == "disabled")
    credential_value: ManagementCredential | None = credential(
        secret,
        revoked=failure == "revoked",
        expires_at=NOW + (timedelta(hours=1) if failure == "expired" else timedelta(days=1)),
    )
    if failure == "unknown":
        credential_value = None
    if failure == "wrong":
        token = token.rsplit("_", 1)[0] + "_wrong-secret"
    result = await ManagementAuthenticator(
        Factory(principal_value, credential_value), PEPPER
    ).authenticate(token, now=NOW + (timedelta(hours=2) if failure == "expired" else timedelta()))
    assert result is None


@pytest.mark.asyncio
async def test_valid_authentication_returns_ids_scopes_and_capability() -> None:
    token, secret = generate_bearer_token(CREDENTIAL_ID)
    result = await ManagementAuthenticator(
        Factory(principal(), credential(secret, expires_at=NOW + timedelta(days=1))), PEPPER
    ).authenticate(token, now=NOW)
    assert result is not None
    assert result.principal_id == PRINCIPAL_ID
    assert result.credential_id == CREDENTIAL_ID
    assert result.authorized_tenant_ids == frozenset({TENANT_ID})
    assert result.can_manage_principals
