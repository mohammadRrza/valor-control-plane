from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from valor.management_audit.domain.audit_record import (
    ManagementAuditAction,
    ManagementAuditOutcome,
    ManagementAuditRecord,
    ManagementAuditResourceType,
)
from valor.management_audit.domain.fingerprints import (
    runtime_credential_fingerprint,
    runtime_principal_fingerprint,
)
from valor.runtime_identity.application.errors import (
    InvalidRuntimeIdentityCommand,
    RuntimeBindingNotFound,
    RuntimeCredentialNotFound,
    RuntimePrincipalManagementDenied,
    RuntimePrincipalNotFound,
)
from valor.runtime_identity.application.ports import (
    RuntimeIdentityUnitOfWork,
    RuntimeIdentityUnitOfWorkFactory,
)
from valor.runtime_identity.application.secrets import (
    generate_runtime_bearer_token,
    runtime_secret_verifier,
)
from valor.runtime_identity.domain.models import RuntimeCredential, RuntimePrincipal


@dataclass(frozen=True, slots=True)
class RuntimeIdentityActor:
    principal_id: UUID
    can_manage_principals: bool


@dataclass(frozen=True, slots=True)
class IssuedRuntimeCredential:
    credential: RuntimeCredential
    bearer_token: str


@dataclass(frozen=True, slots=True)
class CreateRuntimePrincipalCommand:
    actor: RuntimeIdentityActor
    tenant_id: UUID
    agent_id: UUID
    label: str | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class IssueRuntimeCredentialCommand:
    actor: RuntimeIdentityActor
    principal_id: UUID
    label: str | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class RuntimeCredentialCommand:
    actor: RuntimeIdentityActor
    principal_id: UUID
    credential_id: UUID


class RuntimeIdentityService:
    def __init__(
        self,
        uow_factory: RuntimeIdentityUnitOfWorkFactory,
        *,
        pepper: str,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow_factory = uow_factory
        self._pepper = pepper
        self._id_factory = id_factory
        self._clock = clock

    async def create_principal(
        self, command: CreateRuntimePrincipalCommand
    ) -> tuple[RuntimePrincipal, IssuedRuntimeCredential]:
        self._require_manager(command.actor)
        now = self._clock()
        self._validate_expiry(command.expires_at, now)
        async with self._uow_factory() as uow:
            if not await uow.bindings.exists(command.tenant_id, command.agent_id):
                raise RuntimeBindingNotFound
            principal = RuntimePrincipal(
                self._id_factory(), command.tenant_id, command.agent_id, now
            )
            issued = self._new_credential(
                principal.principal_id, command.label, command.expires_at, now
            )
            await uow.principals.add(principal)
            await uow.credentials.add(issued.credential)
            await self._audit_principal(
                uow,
                command.actor.principal_id,
                principal,
                None,
                ManagementAuditAction.RUNTIME_PRINCIPAL_CREATED,
                now,
            )
            await self._audit_credential(
                uow,
                command.actor.principal_id,
                principal.tenant_id,
                issued.credential,
                None,
                ManagementAuditAction.RUNTIME_CREDENTIAL_ISSUED,
                now,
            )
            await uow.commit()
        return principal, issued

    async def get_principal(
        self, actor: RuntimeIdentityActor, principal_id: UUID
    ) -> RuntimePrincipal:
        self._require_manager(actor)
        async with self._uow_factory() as uow:
            value = await uow.principals.get(principal_id)
        if value is None:
            raise RuntimePrincipalNotFound
        return value

    async def issue_credential(
        self, command: IssueRuntimeCredentialCommand
    ) -> IssuedRuntimeCredential:
        self._require_manager(command.actor)
        now = self._clock()
        self._validate_expiry(command.expires_at, now)
        async with self._uow_factory() as uow:
            principal = await uow.principals.get(command.principal_id)
            if principal is None or not principal.is_active:
                raise RuntimePrincipalNotFound
            issued = self._new_credential(
                principal.principal_id, command.label, command.expires_at, now
            )
            await uow.credentials.add(issued.credential)
            await self._audit_credential(
                uow,
                command.actor.principal_id,
                principal.tenant_id,
                issued.credential,
                None,
                ManagementAuditAction.RUNTIME_CREDENTIAL_ISSUED,
                now,
            )
            await uow.commit()
        return issued

    async def revoke_credential(self, command: RuntimeCredentialCommand) -> RuntimeCredential:
        self._require_manager(command.actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            principal = await uow.principals.get(command.principal_id)
            credential = await uow.credentials.get(command.credential_id)
            if principal is None:
                raise RuntimePrincipalNotFound
            if (
                credential is None
                or credential.principal_id != principal.principal_id
                or credential.revoked_at is not None
            ):
                raise RuntimeCredentialNotFound
            revoked = credential.revoke(now)
            await uow.credentials.revoke(revoked)
            await self._audit_credential(
                uow,
                command.actor.principal_id,
                principal.tenant_id,
                revoked,
                credential,
                ManagementAuditAction.RUNTIME_CREDENTIAL_REVOKED,
                now,
            )
            await uow.commit()
        return revoked

    async def disable_principal(
        self, actor: RuntimeIdentityActor, principal_id: UUID
    ) -> RuntimePrincipal:
        self._require_manager(actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            principal = await uow.principals.get(principal_id)
            if principal is None or not principal.is_active:
                raise RuntimePrincipalNotFound
            disabled = principal.disable(now)
            await uow.principals.disable(disabled)
            await self._audit_principal(
                uow,
                actor.principal_id,
                disabled,
                principal,
                ManagementAuditAction.RUNTIME_PRINCIPAL_DISABLED,
                now,
            )
            await uow.commit()
        return disabled

    def _new_credential(
        self, principal_id: UUID, label: str | None, expires_at: datetime | None, now: datetime
    ) -> IssuedRuntimeCredential:
        credential_id = self._id_factory()
        token, secret = generate_runtime_bearer_token(credential_id)
        return IssuedRuntimeCredential(
            RuntimeCredential(
                credential_id,
                principal_id,
                runtime_secret_verifier(secret, self._pepper),
                label,
                now,
                expires_at,
            ),
            token,
        )

    @staticmethod
    def _validate_expiry(expires_at: datetime | None, now: datetime) -> None:
        if expires_at is not None and (
            expires_at.tzinfo is None or expires_at.utcoffset() is None or expires_at <= now
        ):
            raise InvalidRuntimeIdentityCommand(
                "expires_at must be a future timezone-aware timestamp"
            )

    @staticmethod
    def _require_manager(actor: RuntimeIdentityActor) -> None:
        if not actor.can_manage_principals:
            raise RuntimePrincipalManagementDenied

    async def _audit_principal(
        self,
        uow: RuntimeIdentityUnitOfWork,
        actor: UUID,
        value: RuntimePrincipal,
        before: RuntimePrincipal | None,
        action: ManagementAuditAction,
        now: datetime,
    ) -> None:
        def fingerprint(principal: RuntimePrincipal) -> str:
            return runtime_principal_fingerprint(
                principal_id=principal.principal_id,
                tenant_id=principal.tenant_id,
                agent_id=principal.agent_id,
                disabled=not principal.is_active,
            )

        await uow.audits.append(
            ManagementAuditRecord(
                self._id_factory(),
                str(actor),
                value.tenant_id,
                action,
                ManagementAuditResourceType.RUNTIME_PRINCIPAL,
                value.principal_id,
                ManagementAuditOutcome.SUCCEEDED,
                now,
                None if before is None else fingerprint(before),
                fingerprint(value),
            )
        )

    async def _audit_credential(
        self,
        uow: RuntimeIdentityUnitOfWork,
        actor: UUID,
        tenant_id: UUID,
        value: RuntimeCredential,
        before: RuntimeCredential | None,
        action: ManagementAuditAction,
        now: datetime,
    ) -> None:
        def fingerprint(credential: RuntimeCredential) -> str:
            return runtime_credential_fingerprint(
                credential_id=credential.credential_id,
                principal_id=credential.principal_id,
                label=credential.label,
                created_at=credential.created_at.isoformat(),
                expires_at=(
                    None if credential.expires_at is None else credential.expires_at.isoformat()
                ),
                revoked=credential.revoked_at is not None,
            )

        await uow.audits.append(
            ManagementAuditRecord(
                self._id_factory(),
                str(actor),
                tenant_id,
                action,
                ManagementAuditResourceType.RUNTIME_CREDENTIAL,
                value.credential_id,
                ManagementAuditOutcome.SUCCEEDED,
                now,
                None if before is None else fingerprint(before),
                fingerprint(value),
            )
        )
