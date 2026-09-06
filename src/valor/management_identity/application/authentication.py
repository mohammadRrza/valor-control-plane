from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from valor.management_identity.application.ports import (
    ManagementIdentityUnitOfWork,
    ManagementIdentityUnitOfWorkFactory,
)
from valor.management_identity.application.secrets import parse_bearer_token, verifier_matches
from valor.management_identity.domain.authentication_evidence import (
    ManagementAuthenticationEvidence,
    ManagementAuthenticationOutcome,
    hourly_bucket,
)


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
            if credential is None:
                return None
            principal = await uow.principals.get(credential.principal_id)
            if principal is None:
                return None
            if not verifier_matches(secret, self._pepper, credential.secret_verifier):
                await self._observe(
                    uow,
                    credential_id,
                    credential.principal_id,
                    ManagementAuthenticationOutcome.CREDENTIAL_MISMATCH,
                    at,
                )
                return None
            if credential.revoked_at is not None:
                await self._observe(
                    uow,
                    credential_id,
                    credential.principal_id,
                    ManagementAuthenticationOutcome.REVOKED,
                    at,
                )
                return None
            if credential.expires_at is not None and at >= credential.expires_at:
                await self._observe(
                    uow,
                    credential_id,
                    credential.principal_id,
                    ManagementAuthenticationOutcome.EXPIRED,
                    at,
                )
                return None
            if not principal.is_active:
                await self._observe(
                    uow,
                    credential_id,
                    credential.principal_id,
                    ManagementAuthenticationOutcome.PRINCIPAL_DISABLED,
                    at,
                )
                return None
            await self._observe(
                uow,
                credential_id,
                credential.principal_id,
                ManagementAuthenticationOutcome.SUCCEEDED,
                at,
            )
            return AuthenticatedManagementIdentity(
                principal.principal_id,
                credential.credential_id,
                principal.tenant_ids,
                principal.can_manage_principals,
            )

    @staticmethod
    async def _observe(
        uow: ManagementIdentityUnitOfWork,
        credential_id: UUID,
        principal_id: UUID,
        outcome: ManagementAuthenticationOutcome,
        at: datetime,
    ) -> None:
        await uow.authentication_evidence.observe(
            ManagementAuthenticationEvidence(
                credential_id,
                principal_id,
                outcome,
                hourly_bucket(at),
                at,
            )
        )
        await uow.commit()
