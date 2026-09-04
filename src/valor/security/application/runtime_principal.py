"""Authenticated runtime workload identity without credential material."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RuntimePrincipal:
    principal_id: str
    tenant_id: UUID
    agent_id: UUID
    usage_limit: int
    per_invocation_allowance: int

    def __post_init__(self) -> None:
        if not self.principal_id.strip():
            raise ValueError("runtime principal_id must not be empty")
        if self.usage_limit <= 0 or self.per_invocation_allowance <= 0:
            raise ValueError("runtime usage limit and allowance must be positive")
        if self.per_invocation_allowance > self.usage_limit:
            raise ValueError("runtime allowance must not exceed usage limit")
