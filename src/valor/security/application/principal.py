"""Authenticated principal passed beyond transport-specific authentication."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class PrincipalKind(StrEnum):
    MANAGEMENT = "management"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    principal_id: UUID
    credential_id: UUID
    principal_kind: PrincipalKind
    authorized_tenant_ids: frozenset[UUID]
    can_manage_principals: bool

    def __post_init__(self) -> None:
        if self.principal_id.int == 0 or self.credential_id.int == 0:
            raise ValueError("principal and credential IDs must not be nil UUIDs")
