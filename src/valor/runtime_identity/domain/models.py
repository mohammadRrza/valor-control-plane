from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True, slots=True)
class RuntimePrincipal:
    principal_id: UUID
    tenant_id: UUID
    agent_id: UUID
    created_at: datetime
    disabled_at: datetime | None = None
    daily_usage_limit_units: int | None = None
    per_invocation_allowance_units: int | None = None
    legacy_runtime_principal_id: str | None = None
    identity_continuity_bound_at: datetime | None = None

    def __post_init__(self) -> None:
        if not _aware(self.created_at) or (
            self.disabled_at is not None and not _aware(self.disabled_at)
        ):
            raise ValueError("principal timestamps must be timezone-aware")
        daily = self.daily_usage_limit_units
        allowance = self.per_invocation_allowance_units
        configured = (daily is not None, allowance is not None)
        if configured[0] != configured[1]:
            raise ValueError("runtime usage limits must be configured together")
        if (
            daily is not None
            and allowance is not None
            and (daily <= 0 or allowance <= 0 or allowance > daily)
        ):
            raise ValueError("runtime usage limits are invalid")
        legacy = (
            self.legacy_runtime_principal_id.strip()
            if self.legacy_runtime_principal_id is not None
            else None
        )
        object.__setattr__(self, "legacy_runtime_principal_id", legacy)
        if (legacy is None) != (self.identity_continuity_bound_at is None):
            raise ValueError("legacy identity and binding time must be configured together")
        if legacy is not None and (not legacy or len(legacy) > 255):
            raise ValueError("legacy runtime principal ID must be 1 to 255 characters")
        if self.identity_continuity_bound_at is not None and not _aware(
            self.identity_continuity_bound_at
        ):
            raise ValueError("identity continuity binding time must be timezone-aware")

    @classmethod
    def create(
        cls,
        principal_id: UUID,
        tenant_id: UUID,
        agent_id: UUID,
        created_at: datetime,
        daily_usage_limit_units: int,
        per_invocation_allowance_units: int,
    ) -> "RuntimePrincipal":
        return cls(
            principal_id,
            tenant_id,
            agent_id,
            created_at,
            daily_usage_limit_units=daily_usage_limit_units,
            per_invocation_allowance_units=per_invocation_allowance_units,
        )

    @property
    def is_active(self) -> bool:
        return self.disabled_at is None

    @property
    def state(self) -> str:
        return "active" if self.is_active else "disabled"

    @property
    def usage_limits_configured(self) -> bool:
        return self.daily_usage_limit_units is not None

    @property
    def identity_continuity_ready(self) -> bool:
        return self.legacy_runtime_principal_id is not None

    @property
    def continuity_identity_ids(self) -> frozenset[str]:
        values = [str(self.principal_id)]
        if self.legacy_runtime_principal_id is not None:
            values.append(self.legacy_runtime_principal_id)
        return frozenset(values)

    def bind_identity_continuity(self, legacy_id: str, at: datetime) -> "RuntimePrincipal":
        if not self.is_active:
            raise ValueError("disabled principals cannot be prepared for cutover")
        if self.identity_continuity_ready:
            raise ValueError("runtime identity continuity is already bound")
        return replace(
            self,
            legacy_runtime_principal_id=legacy_id,
            identity_continuity_bound_at=at,
        )

    def initialize_usage_limits(
        self, daily_usage_limit_units: int, per_invocation_allowance_units: int
    ) -> "RuntimePrincipal":
        if not self.is_active:
            raise ValueError("disabled principals cannot be prepared for cutover")
        if self.usage_limits_configured:
            raise ValueError("runtime usage limits are already initialized")
        return replace(
            self,
            daily_usage_limit_units=daily_usage_limit_units,
            per_invocation_allowance_units=per_invocation_allowance_units,
        )

    def disable(self, at: datetime) -> "RuntimePrincipal":
        if not self.is_active:
            raise ValueError("principal is already disabled")
        if not _aware(at):
            raise ValueError("disabled_at must be timezone-aware")
        return replace(self, disabled_at=at)


@dataclass(frozen=True, slots=True)
class RuntimeCredential:
    credential_id: UUID
    principal_id: UUID
    secret_verifier: str
    label: str | None
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        label = " ".join(self.label.split()) if self.label is not None else None
        object.__setattr__(self, "label", label or None)
        if label is not None and len(label) > 100:
            raise ValueError("credential label must not exceed 100 characters")
        if len(self.secret_verifier) != 64 or any(
            c not in "0123456789abcdef" for c in self.secret_verifier
        ):
            raise ValueError("secret_verifier must be lowercase HMAC-SHA256 hex")
        for value in (self.created_at, self.expires_at, self.revoked_at):
            if value is not None and not _aware(value):
                raise ValueError("credential timestamps must be timezone-aware")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")

    def is_usable_at(self, at: datetime, *, principal_active: bool = True) -> bool:
        return (
            principal_active
            and self.revoked_at is None
            and (self.expires_at is None or at < self.expires_at)
        )

    def revoke(self, at: datetime) -> "RuntimeCredential":
        if self.revoked_at is not None:
            raise ValueError("credential is already revoked")
        if not _aware(at):
            raise ValueError("revoked_at must be timezone-aware")
        return replace(self, revoked_at=at)
