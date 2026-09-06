from uuid import UUID, uuid4

import pytest

from valor.security.application.authorization import authorize_tenant
from valor.security.application.errors import TenantManagementAccessDenied
from valor.security.application.principal import AuthenticatedPrincipal, PrincipalKind


def principal(*tenant_ids: UUID) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        principal_id=UUID("11111111-1111-4111-8111-111111111111"),
        credential_id=UUID("22222222-2222-4222-8222-222222222222"),
        principal_kind=PrincipalKind.MANAGEMENT,
        authorized_tenant_ids=frozenset(tenant_ids),
        can_manage_principals=False,
    )


def test_principal_authorized_for_exact_tenant_succeeds() -> None:
    tenant_id = UUID("11111111-1111-4111-8111-111111111111")
    authorize_tenant(principal(tenant_id), UUID(str(tenant_id)))


def test_principal_unauthorized_for_tenant_fails() -> None:
    with pytest.raises(TenantManagementAccessDenied):
        authorize_tenant(principal(uuid4()), uuid4())


def test_empty_tenant_scope_fails_closed() -> None:
    with pytest.raises(TenantManagementAccessDenied):
        authorize_tenant(principal(), uuid4())


def test_authorization_state_contains_no_bearer_credential() -> None:
    management_principal = principal(uuid4())
    assert not hasattr(management_principal, "token")
    assert "Bearer" not in repr(management_principal)
