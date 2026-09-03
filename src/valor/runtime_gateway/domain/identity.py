"""Runtime-local identities used at bounded-context boundaries."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class InvocationId:
    value: UUID


@dataclass(frozen=True, slots=True)
class TenantId:
    value: UUID


@dataclass(frozen=True, slots=True)
class AgentId:
    value: UUID


@dataclass(frozen=True, slots=True)
class ModelId:
    value: UUID
