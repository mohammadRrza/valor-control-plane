from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from secrets import compare_digest
from uuid import UUID, uuid4

from valor.management_audit.domain.audit_record import (
    ManagementAuditAction,
    ManagementAuditOutcome,
    ManagementAuditRecord,
    ManagementAuditResourceType,
)
from valor.management_audit.domain.fingerprints import (
    management_credential_fingerprint,
    management_principal_fingerprint,
)
from valor.management_identity.application.errors import (
    BootstrapAlreadyCompleted,
    BootstrapAuthenticationFailed,
    InvalidManagementIdentityCommand,
    LastPrincipalManagerConflict,
    ManagementCredentialNotFound,
    ManagementPrincipalNotFound,
    PrincipalManagementDenied,
)
from valor.management_identity.application.ports import (
    ManagementIdentityUnitOfWork,
    ManagementIdentityUnitOfWorkFactory,
)
from valor.management_identity.application.secrets import generate_bearer_token, secret_verifier
from valor.management_identity.domain.models import ManagementCredential, ManagementPrincipal


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ManagementActor:
    principal_id: UUID
    can_manage_principals: bool


@dataclass(frozen=True, slots=True)
class IssuedCredential:
    credential: ManagementCredential
    bearer_token: str


@dataclass(frozen=True, slots=True)
class BootstrapCommand:
    supplied_token: str
    display_name: str
    tenant_ids: frozenset[UUID]


@dataclass(frozen=True, slots=True)
class CreatePrincipalCommand:
    actor: ManagementActor
    display_name: str
    tenant_ids: frozenset[UUID]
    can_manage_principals: bool


@dataclass(frozen=True, slots=True)
class IssueCredentialCommand:
    actor: ManagementActor
    principal_id: UUID
    label: str | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class SetScopesCommand:
    actor: ManagementActor
    principal_id: UUID
    tenant_ids: frozenset[UUID]


@dataclass(frozen=True, slots=True)
class RevokeCredentialCommand:
    actor: ManagementActor
    principal_id: UUID
    credential_id: UUID


@dataclass(frozen=True, slots=True)
class DisablePrincipalCommand:
    actor: ManagementActor
    principal_id: UUID


class ManagementIdentityService:
    def __init__(
        self,
        uow_factory: ManagementIdentityUnitOfWorkFactory,
        *,
        pepper: str,
        bootstrap_token: str,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._uow_factory = uow_factory
        self._pepper = pepper
        self._bootstrap_token = bootstrap_token
        self._id_factory = id_factory
        self._clock = clock

    async def bootstrap(
        self, command: BootstrapCommand
    ) -> tuple[ManagementPrincipal, IssuedCredential]:
        if not compare_digest(command.supplied_token, self._bootstrap_token):
            raise BootstrapAuthenticationFailed
        now = self._clock()
        async with self._uow_factory() as uow:
            await uow.lock_management_state()
            if await uow.principals.count() != 0:
                raise BootstrapAlreadyCompleted
            await self._require_tenants(uow, command.tenant_ids)
            principal = self._new_principal(command.display_name, True, command.tenant_ids, now)
            issued = self._new_credential(principal.principal_id, "bootstrap", None, now)
            await uow.principals.add(principal)
            await uow.credentials.add(issued.credential)
            await uow.commit()
        return principal, issued

    async def create_principal(self, command: CreatePrincipalCommand) -> ManagementPrincipal:
        self._require_manager(command.actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            await self._require_tenants(uow, command.tenant_ids)
            principal = self._new_principal(
                command.display_name,
                command.can_manage_principals,
                command.tenant_ids,
                now,
            )
            await uow.principals.add(principal)
            await self._audit_principal(
                uow,
                command.actor.principal_id,
                principal,
                None,
                ManagementAuditAction.MANAGEMENT_PRINCIPAL_CREATED,
                now,
            )
            await uow.commit()
        return principal

    async def get_principal(
        self, actor: ManagementActor, principal_id: UUID
    ) -> ManagementPrincipal:
        self._require_manager(actor)
        async with self._uow_factory() as uow:
            principal = await uow.principals.get(principal_id)
        if principal is None:
            raise ManagementPrincipalNotFound
        return principal

    async def issue_credential(self, command: IssueCredentialCommand) -> IssuedCredential:
        self._require_manager(command.actor)
        now = self._clock()
        if command.expires_at is not None:
            if command.expires_at.tzinfo is None or command.expires_at.utcoffset() is None:
                raise InvalidManagementIdentityCommand("expires_at must include a timezone offset")
            if command.expires_at <= now:
                raise InvalidManagementIdentityCommand("expires_at must be in the future")
        async with self._uow_factory() as uow:
            principal = await uow.principals.get(command.principal_id)
            if principal is None or not principal.is_active:
                raise ManagementPrincipalNotFound
            issued = self._new_credential(
                principal.principal_id, command.label, command.expires_at, now
            )
            await uow.credentials.add(issued.credential)
            await self._audit_credential(
                uow,
                command.actor.principal_id,
                issued.credential,
                None,
                ManagementAuditAction.MANAGEMENT_CREDENTIAL_ISSUED,
                now,
            )
            await uow.commit()
        return issued

    async def set_scopes(self, command: SetScopesCommand) -> ManagementPrincipal:
        self._require_manager(command.actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            principal = await uow.principals.get(command.principal_id)
            if principal is None:
                raise ManagementPrincipalNotFound
            await self._require_tenants(uow, command.tenant_ids)
            updated = principal.with_tenant_scopes(command.tenant_ids)
            await uow.principals.replace_scopes(updated)
            await self._audit_principal(
                uow,
                command.actor.principal_id,
                updated,
                principal,
                ManagementAuditAction.MANAGEMENT_PRINCIPAL_SCOPES_SET,
                now,
            )
            await uow.commit()
        return updated

    async def revoke_credential(self, command: RevokeCredentialCommand) -> ManagementCredential:
        self._require_manager(command.actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            await uow.lock_management_state()
            principal = await uow.principals.get(command.principal_id)
            credential = await uow.credentials.get(command.credential_id)
            if principal is None:
                raise ManagementPrincipalNotFound
            if credential is None or credential.principal_id != principal.principal_id:
                raise ManagementCredentialNotFound
            if credential.revoked_at is not None:
                raise ManagementCredentialNotFound
            if principal.is_active and principal.can_manage_principals:
                other_manager = await uow.principals.has_recoverable_manager(
                    excluding_principal_id=principal.principal_id
                )
                usable_count = sum(
                    item.credential_id != credential.credential_id and item.is_usable_at(now)
                    for item in await uow.credentials.list_for_principal(principal.principal_id)
                )
                if not other_manager and usable_count == 0:
                    raise LastPrincipalManagerConflict
            revoked = credential.revoke(now)
            await uow.credentials.revoke(revoked)
            await self._audit_credential(
                uow,
                command.actor.principal_id,
                revoked,
                credential,
                ManagementAuditAction.MANAGEMENT_CREDENTIAL_REVOKED,
                now,
            )
            await uow.commit()
        return revoked

    async def disable_principal(self, command: DisablePrincipalCommand) -> ManagementPrincipal:
        self._require_manager(command.actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            await uow.lock_management_state()
            principal = await uow.principals.get(command.principal_id)
            if principal is None or not principal.is_active:
                raise ManagementPrincipalNotFound
            if principal.can_manage_principals and not await uow.principals.has_recoverable_manager(
                excluding_principal_id=principal.principal_id
            ):
                raise LastPrincipalManagerConflict
            disabled = principal.disable(now)
            await uow.principals.disable(disabled)
            await self._audit_principal(
                uow,
                command.actor.principal_id,
                disabled,
                principal,
                ManagementAuditAction.MANAGEMENT_PRINCIPAL_DISABLED,
                now,
            )
            await uow.commit()
        return disabled

    def _new_credential(
        self, principal_id: UUID, label: str | None, expires_at: datetime | None, now: datetime
    ) -> IssuedCredential:
        credential_id = self._id_factory()
        token, secret = generate_bearer_token(credential_id)
        try:
            credential = ManagementCredential(
                credential_id,
                principal_id,
                secret_verifier(secret, self._pepper),
                label,
                now,
                expires_at,
            )
        except ValueError as error:
            raise InvalidManagementIdentityCommand(str(error)) from error
        return IssuedCredential(credential, token)

    def _new_principal(
        self,
        display_name: str,
        can_manage_principals: bool,
        tenant_ids: frozenset[UUID],
        now: datetime,
    ) -> ManagementPrincipal:
        try:
            return ManagementPrincipal(
                self._id_factory(),
                display_name,
                can_manage_principals,
                tenant_ids,
                now,
            )
        except ValueError as error:
            raise InvalidManagementIdentityCommand(str(error)) from error

    @staticmethod
    def _require_manager(actor: ManagementActor) -> None:
        if not actor.can_manage_principals:
            raise PrincipalManagementDenied

    @staticmethod
    async def _require_tenants(
        uow: ManagementIdentityUnitOfWork, tenant_ids: frozenset[UUID]
    ) -> None:
        if tenant_ids and not await uow.tenants.all_exist(tenant_ids):
            raise InvalidManagementIdentityCommand("one or more Tenant scopes do not exist")

    async def _audit_principal(
        self,
        uow: ManagementIdentityUnitOfWork,
        actor_id: UUID,
        after: ManagementPrincipal,
        before: ManagementPrincipal | None,
        action: ManagementAuditAction,
        now: datetime,
    ) -> None:
        await uow.audits.append(
            ManagementAuditRecord(
                self._id_factory(),
                str(actor_id),
                None,
                action,
                ManagementAuditResourceType.MANAGEMENT_PRINCIPAL,
                after.principal_id,
                ManagementAuditOutcome.SUCCEEDED,
                now,
                None if before is None else _principal_fingerprint(before),
                _principal_fingerprint(after),
            )
        )

    async def _audit_credential(
        self,
        uow: ManagementIdentityUnitOfWork,
        actor_id: UUID,
        after: ManagementCredential,
        before: ManagementCredential | None,
        action: ManagementAuditAction,
        now: datetime,
    ) -> None:
        await uow.audits.append(
            ManagementAuditRecord(
                self._id_factory(),
                str(actor_id),
                None,
                action,
                ManagementAuditResourceType.MANAGEMENT_CREDENTIAL,
                after.credential_id,
                ManagementAuditOutcome.SUCCEEDED,
                now,
                None if before is None else _credential_fingerprint(before),
                _credential_fingerprint(after),
            )
        )


def _principal_fingerprint(principal: ManagementPrincipal) -> str:
    return management_principal_fingerprint(
        principal_id=principal.principal_id,
        display_name=principal.display_name,
        tenant_ids=principal.tenant_ids,
        can_manage_principals=principal.can_manage_principals,
        disabled=not principal.is_active,
    )


def _credential_fingerprint(credential: ManagementCredential) -> str:
    return management_credential_fingerprint(
        credential_id=credential.credential_id,
        principal_id=credential.principal_id,
        label=credential.label,
        created_at=credential.created_at.astimezone(UTC).isoformat(),
        expires_at=None
        if credential.expires_at is None
        else credential.expires_at.astimezone(UTC).isoformat(),
        revoked=credential.revoked_at is not None,
    )
