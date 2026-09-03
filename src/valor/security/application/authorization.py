"""Small, fail-closed Tenant management authorization rule."""

from uuid import UUID

from valor.security.application.errors import TenantManagementAccessDenied
from valor.security.application.principal import AuthenticatedPrincipal, PrincipalKind


def authorize_tenant(principal: AuthenticatedPrincipal, tenant_id: UUID) -> None:
    if (
        principal.principal_kind is not PrincipalKind.MANAGEMENT
        or tenant_id not in principal.authorized_tenant_ids
    ):
        raise TenantManagementAccessDenied
