"""Tenant aggregate and value objects."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from valor.identity_tenancy.domain.errors import InvalidTenantName

MAX_TENANT_NAME_LENGTH = 100


@dataclass(frozen=True, slots=True)
class TenantId:
    value: UUID


@dataclass(frozen=True, slots=True)
class TenantName:
    value: str
    normalized: str = field(init=False)

    def __post_init__(self) -> None:
        canonical = " ".join(self.value.split())
        if not canonical:
            raise InvalidTenantName("Tenant name must not be empty.")
        if len(canonical) > MAX_TENANT_NAME_LENGTH:
            raise InvalidTenantName(
                f"Tenant name must be at most {MAX_TENANT_NAME_LENGTH} characters."
            )
        object.__setattr__(self, "value", canonical)
        object.__setattr__(self, "normalized", canonical.casefold())


@dataclass(frozen=True, slots=True)
class Tenant:
    id: TenantId
    name: TenantName
    created_at: datetime

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("Tenant creation time must be timezone-aware.")

    @classmethod
    def create(cls, tenant_id: TenantId, name: str, created_at: datetime) -> "Tenant":
        return cls(id=tenant_id, name=TenantName(name), created_at=created_at)
