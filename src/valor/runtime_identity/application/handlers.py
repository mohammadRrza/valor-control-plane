from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    RuntimeIdentityContinuityConflict,
    RuntimePrincipalManagementDenied,
    RuntimePrincipalNotFound,
    RuntimeUsageLimitsAlreadyInitialized,
)
from valor.runtime_identity.application.ports import (
    LegacyRuntimeConfigurationPort,
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
    daily_usage_limit_units: int
    per_invocation_allowance_units: int
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


@dataclass(frozen=True, slots=True)
class InitializeRuntimeUsageLimitsCommand:
    actor: RuntimeIdentityActor
    principal_id: UUID
    daily_usage_limit_units: int
    per_invocation_allowance_units: int


@dataclass(frozen=True, slots=True)
class RuntimePrincipalDetails:
    principal: RuntimePrincipal
    cutover_ready: bool


@dataclass(frozen=True, slots=True)
class RuntimeIdentityContinuityCommand:
    actor: RuntimeIdentityActor
    principal_id: UUID
    legacy_runtime_principal_id: str


@dataclass(frozen=True, slots=True)
class RuntimeIdentityContinuityPreflight:
    principal_id: UUID
    legacy_runtime_principal_id: str
    static_identity_exists: bool
    tenant_binding_matches: bool
    agent_binding_matches: bool
    legacy_identity_unclaimed: bool
    principal_unbound: bool
    historical_invocation_count: int
    same_day_attributed_usage_units: int
    usage_limits_match: bool
    historical_bindings_consistent: bool
    cutover_ready: bool
    safe_to_bind: bool


class RuntimeIdentityService:
    def __init__(
        self,
        uow_factory: RuntimeIdentityUnitOfWorkFactory,
        *,
        pepper: str,
        legacy_configurations: LegacyRuntimeConfigurationPort | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow_factory = uow_factory
        self._pepper = pepper
        self._legacy_configurations = legacy_configurations
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
            try:
                principal = RuntimePrincipal.create(
                    self._id_factory(),
                    command.tenant_id,
                    command.agent_id,
                    now,
                    command.daily_usage_limit_units,
                    command.per_invocation_allowance_units,
                )
            except ValueError as exc:
                raise InvalidRuntimeIdentityCommand(str(exc)) from exc
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
    ) -> RuntimePrincipalDetails:
        self._require_manager(actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            value = await uow.principals.get(principal_id)
            has_usable_credential = (
                False
                if value is None
                else await uow.credentials.has_potentially_usable(principal_id, now)
            )
        if value is None:
            raise RuntimePrincipalNotFound
        return RuntimePrincipalDetails(
            value,
            value.is_active and value.usage_limits_configured and has_usable_credential,
        )

    async def preflight_identity_continuity(
        self, command: RuntimeIdentityContinuityCommand
    ) -> RuntimeIdentityContinuityPreflight:
        self._require_manager(command.actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            principal = await uow.principals.get(command.principal_id)
            if principal is None or not principal.is_active:
                raise RuntimePrincipalNotFound
            return await self._continuity_preflight(uow, principal, command, now)

    async def bind_identity_continuity(
        self, command: RuntimeIdentityContinuityCommand
    ) -> RuntimePrincipal:
        self._require_manager(command.actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            await uow.principals.lock_legacy_identity(command.legacy_runtime_principal_id)
            principal = await uow.principals.get_for_update(command.principal_id)
            if principal is None or not principal.is_active:
                raise RuntimePrincipalNotFound
            if (
                principal.identity_continuity_ready
                or await uow.principals.legacy_identity_is_claimed(
                    command.legacy_runtime_principal_id
                )
            ):
                raise RuntimeIdentityContinuityConflict
            preflight = await self._continuity_preflight(uow, principal, command, now)
            if not preflight.safe_to_bind:
                raise InvalidRuntimeIdentityCommand(
                    "Runtime identity continuity validation did not pass."
                )
            try:
                bound = principal.bind_identity_continuity(command.legacy_runtime_principal_id, now)
            except ValueError as exc:
                raise InvalidRuntimeIdentityCommand(str(exc)) from exc
            if not await uow.principals.bind_identity_continuity(bound):
                raise RuntimeIdentityContinuityConflict
            await self._audit_principal(
                uow,
                command.actor.principal_id,
                bound,
                principal,
                ManagementAuditAction.RUNTIME_PRINCIPAL_IDENTITY_CONTINUITY_BOUND,
                now,
            )
            await uow.commit()
        return bound

    async def continuity_usage_total(
        self,
        actor: RuntimeIdentityActor,
        principal_id: UUID,
        day_start: datetime,
        day_end: datetime,
    ) -> int:
        self._require_manager(actor)
        async with self._uow_factory() as uow:
            principal = await uow.principals.get(principal_id)
            if principal is None:
                raise RuntimePrincipalNotFound
            return await uow.invocations.consumed_total_units(
                principal.continuity_identity_ids, day_start, day_end
            )

    async def _continuity_preflight(
        self,
        uow: RuntimeIdentityUnitOfWork,
        principal: RuntimePrincipal,
        command: RuntimeIdentityContinuityCommand,
        now: datetime,
    ) -> RuntimeIdentityContinuityPreflight:
        legacy = (
            None
            if self._legacy_configurations is None
            else self._legacy_configurations.get(command.legacy_runtime_principal_id)
        )
        day_start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        facts = await uow.invocations.inspect(
            legacy_id=command.legacy_runtime_principal_id,
            canonical_id=str(principal.principal_id),
            tenant_id=principal.tenant_id,
            agent_id=principal.agent_id,
            day_start=day_start,
            day_end=day_start + timedelta(days=1),
        )
        tenant_matches = legacy is not None and legacy.tenant_id == principal.tenant_id
        agent_matches = legacy is not None and legacy.agent_id == principal.agent_id
        limits_match = (
            legacy is not None
            and principal.daily_usage_limit_units == legacy.daily_usage_limit_units
            and principal.per_invocation_allowance_units == legacy.per_invocation_allowance_units
        )
        unclaimed = not await uow.principals.legacy_identity_is_claimed(
            command.legacy_runtime_principal_id
        )
        has_credential = await uow.credentials.has_potentially_usable(principal.principal_id, now)
        cutover_ready = principal.is_active and principal.usage_limits_configured and has_credential
        consistent = not facts.legacy_binding_mismatch and not facts.canonical_binding_mismatch
        principal_unbound = not principal.identity_continuity_ready
        safe = all(
            (
                legacy is not None,
                tenant_matches,
                agent_matches,
                unclaimed,
                principal_unbound,
                limits_match,
                consistent,
                cutover_ready,
            )
        )
        return RuntimeIdentityContinuityPreflight(
            principal.principal_id,
            command.legacy_runtime_principal_id,
            legacy is not None,
            tenant_matches,
            agent_matches,
            unclaimed,
            principal_unbound,
            facts.historical_invocation_count,
            facts.same_day_attributed_usage_units,
            limits_match,
            consistent,
            cutover_ready,
            safe,
        )

    async def initialize_usage_limits(
        self, command: InitializeRuntimeUsageLimitsCommand
    ) -> RuntimePrincipal:
        self._require_manager(command.actor)
        now = self._clock()
        async with self._uow_factory() as uow:
            principal = await uow.principals.get(command.principal_id)
            if principal is None or not principal.is_active:
                raise RuntimePrincipalNotFound
            if principal.usage_limits_configured:
                raise RuntimeUsageLimitsAlreadyInitialized
            try:
                configured = principal.initialize_usage_limits(
                    command.daily_usage_limit_units,
                    command.per_invocation_allowance_units,
                )
            except ValueError as exc:
                raise InvalidRuntimeIdentityCommand(str(exc)) from exc
            if not await uow.principals.initialize_usage_limits(configured):
                raise RuntimeUsageLimitsAlreadyInitialized
            await self._audit_principal(
                uow,
                command.actor.principal_id,
                configured,
                principal,
                ManagementAuditAction.RUNTIME_PRINCIPAL_USAGE_LIMITS_INITIALIZED,
                now,
            )
            await uow.commit()
        return configured

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
                daily_usage_limit_units=principal.daily_usage_limit_units,
                per_invocation_allowance_units=principal.per_invocation_allowance_units,
                legacy_runtime_principal_id=principal.legacy_runtime_principal_id,
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
