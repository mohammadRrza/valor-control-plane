from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID


def normalize_display_name(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("display_name must not be empty")
    if len(normalized) > 100:
        raise ValueError("display_name must not exceed 100 characters")
    return normalized


@dataclass(frozen=True, slots=True)
class ManagementPrincipal:
    principal_id: UUID
    display_name: str
    can_manage_principals: bool
    tenant_ids: frozenset[UUID]
    created_at: datetime
    disabled_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "display_name", normalize_display_name(self.display_name))
        for timestamp in (self.created_at, self.disabled_at):
            if timestamp is not None and (
                timestamp.tzinfo is None or timestamp.utcoffset() is None
            ):
                raise ValueError("principal timestamps must be timezone-aware")

    @property
    def is_active(self) -> bool:
        return self.disabled_at is None

    def disable(self, at: datetime) -> "ManagementPrincipal":
        if not self.is_active:
            raise ValueError("principal is already disabled")
        return replace(self, disabled_at=at)

    def with_tenant_scopes(self, tenant_ids: frozenset[UUID]) -> "ManagementPrincipal":
        return replace(self, tenant_ids=tenant_ids)


@dataclass(frozen=True, slots=True)
class ManagementCredential:
    credential_id: UUID
    principal_id: UUID
    secret_verifier: str
    label: str | None
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        label = " ".join(self.label.split()) if self.label is not None else None
        if label == "":
            label = None
        if label is not None and len(label) > 100:
            raise ValueError("credential label must not exceed 100 characters")
        object.__setattr__(self, "label", label)
        if len(self.secret_verifier) != 64 or any(
            character not in "0123456789abcdef" for character in self.secret_verifier
        ):
            raise ValueError("secret_verifier must be lowercase HMAC-SHA256 hex")
        for timestamp in (self.created_at, self.expires_at, self.revoked_at):
            if timestamp is not None and (
                timestamp.tzinfo is None or timestamp.utcoffset() is None
            ):
                raise ValueError("credential timestamps must be timezone-aware")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")

    def is_usable_at(self, at: datetime) -> bool:
        return self.revoked_at is None and (self.expires_at is None or at < self.expires_at)

    def revoke(self, at: datetime) -> "ManagementCredential":
        if self.revoked_at is not None:
            raise ValueError("credential is already revoked")
        return replace(self, revoked_at=at)
