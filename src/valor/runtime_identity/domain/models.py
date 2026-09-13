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

    def __post_init__(self) -> None:
        if not _aware(self.created_at) or (
            self.disabled_at is not None and not _aware(self.disabled_at)
        ):
            raise ValueError("principal timestamps must be timezone-aware")

    @property
    def is_active(self) -> bool:
        return self.disabled_at is None

    @property
    def state(self) -> str:
        return "active" if self.is_active else "disabled"

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
