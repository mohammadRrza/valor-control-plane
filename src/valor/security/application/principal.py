"""Authenticated principal passed beyond transport-specific authentication."""

from dataclasses import dataclass
from enum import StrEnum


class PrincipalKind(StrEnum):
    MANAGEMENT = "management"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    principal_id: str
    principal_kind: PrincipalKind

    def __post_init__(self) -> None:
        if not self.principal_id.strip():
            raise ValueError("principal_id must not be empty")
