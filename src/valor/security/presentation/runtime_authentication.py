"""Bearer authentication for configuration-backed runtime principals."""

from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from valor.security.application.errors import RuntimeAuthenticationFailed
from valor.security.application.runtime_principal import RuntimePrincipal

runtime_bearer = HTTPBearer(auto_error=False)


def require_runtime_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(runtime_bearer)],
) -> RuntimePrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise RuntimeAuthenticationFailed

    supplied = credentials.credentials.encode("utf-8")
    matches = [
        configured
        for configured in request.app.state.settings.runtime_auth.principals
        if compare_digest(
            supplied,
            configured.credential.get_secret_value().encode("utf-8"),
        )
    ]
    if len(matches) != 1:
        raise RuntimeAuthenticationFailed
    matched = matches[0]
    return RuntimePrincipal(matched.principal_id, matched.tenant_id, matched.agent_id)
