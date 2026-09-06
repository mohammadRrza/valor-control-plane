from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from valor.management_identity.application.ports import ManagementIdentityUnitOfWorkFactory
from valor.management_identity.application.secrets import parse_bearer_token, verifier_matches


@dataclass(frozen=True, slots=True)
class AuthenticatedManagementIdentity:
    principal_id: UUID
    credential_id: UUID
    authorized_tenant_ids: frozenset[UUID]
    can_manage_principals: bool


class ManagementAuthenticator:
    def __init__(
        self,
        uow_factory: ManagementIdentityUnitOfWorkFactory,
        pepper: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._pepper = pepper

    async def authenticate(
        self, token: str, *, now: datetime | None = None
    ) -> AuthenticatedManagementIdentity | None:
        parsed = parse_bearer_token(token)
        if parsed is None:
            return None
        credential_id, secret = parsed
        at = now or datetime.now(UTC)
        async with self._uow_factory() as uow:
            credential = await uow.credentials.get(credential_id)
            if credential is None or not credential.is_usable_at(at):
                return None
            principal = await uow.principals.get(credential.principal_id)
            if principal is None or not principal.is_active:
                return None
            if not verifier_matches(secret, self._pepper, credential.secret_verifier):
                return None
            return AuthenticatedManagementIdentity(
                principal.principal_id,
                credential.credential_id,
                principal.tenant_ids,
                principal.can_manage_principals,
            )
