"""Persisted Management bearer authentication dependency."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from valor.security.application.errors import ManagementAuthenticationFailed
from valor.security.application.principal import AuthenticatedPrincipal, PrincipalKind

bearer = HTTPBearer(auto_error=False)


async def require_management_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ManagementAuthenticationFailed

    identity = await request.app.state.management_authenticator.authenticate(
        credentials.credentials
    )
    if identity is None:
        raise ManagementAuthenticationFailed

    return AuthenticatedPrincipal(
        principal_id=identity.principal_id,
        credential_id=identity.credential_id,
        principal_kind=PrincipalKind.MANAGEMENT,
        authorized_tenant_ids=identity.authorized_tenant_ids,
        can_manage_principals=identity.can_manage_principals,
    )
