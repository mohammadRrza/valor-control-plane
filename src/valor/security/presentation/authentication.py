"""Single FastAPI dependency for management bearer authentication."""

from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from valor.security.application.errors import ManagementAuthenticationFailed
from valor.security.application.principal import AuthenticatedPrincipal, PrincipalKind

bearer = HTTPBearer(auto_error=False)


def require_management_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ManagementAuthenticationFailed

    security = request.app.state.settings.security
    supplied = credentials.credentials.encode("utf-8")
    expected = security.management_token.get_secret_value().encode("utf-8")
    if not compare_digest(supplied, expected):
        raise ManagementAuthenticationFailed

    return AuthenticatedPrincipal(
        principal_id=security.management_principal_id,
        principal_kind=PrincipalKind.MANAGEMENT,
        authorized_tenant_ids=security.management_tenant_ids,
    )
