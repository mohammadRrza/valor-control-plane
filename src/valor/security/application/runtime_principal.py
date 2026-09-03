"""Authenticated runtime workload identity without credential material."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RuntimePrincipal:
    principal_id: str
    tenant_id: UUID
    agent_id: UUID

    def __post_init__(self) -> None:
        if not self.principal_id.strip():
            raise ValueError("runtime principal_id must not be empty")
