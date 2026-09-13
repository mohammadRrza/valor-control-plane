from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from valor.runtime_identity.application.secrets import (
    generate_runtime_bearer_token,
    runtime_secret_verifier,
    verify_runtime_secret,
)
from valor.runtime_identity.domain.models import RuntimeCredential, RuntimePrincipal


def test_runtime_principal_disablement_is_terminal() -> None:
    now = datetime.now(UTC)
    principal = RuntimePrincipal(uuid4(), uuid4(), uuid4(), now)
    disabled = principal.disable(now + timedelta(seconds=1))

    assert principal.is_active
    assert disabled.state == "disabled"
    with pytest.raises(ValueError):
        disabled.disable(now + timedelta(seconds=2))


def test_runtime_credential_expiry_boundary_and_disabled_principal() -> None:
    now = datetime.now(UTC)
    credential = RuntimeCredential(
        uuid4(), uuid4(), "a" * 64, "  overlap   key ", now, now + timedelta(hours=1)
    )

    assert credential.label == "overlap key"
    assert credential.is_usable_at(now + timedelta(minutes=59))
    assert not credential.is_usable_at(now + timedelta(hours=1))
    assert not credential.is_usable_at(now, principal_active=False)
    revoked = credential.revoke(now + timedelta(minutes=1))
    assert not revoked.is_usable_at(now + timedelta(minutes=2))
    with pytest.raises(ValueError):
        revoked.revoke(now + timedelta(minutes=3))


def test_runtime_bearer_is_runtime_specific_and_verifier_is_secret_free() -> None:
    token, secret = generate_runtime_bearer_token(uuid4())
    verifier = runtime_secret_verifier(secret, "p" * 32)

    assert token.startswith("valor_runtime_")
    assert secret in token
    assert len(secret) >= 32
    assert verifier != secret
    assert token not in verifier
    assert len(verifier) == 64
    assert verify_runtime_secret(secret, "p" * 32, verifier)
    assert not verify_runtime_secret("wrong", "p" * 32, verifier)
