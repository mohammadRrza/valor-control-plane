from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PermissionId:
    value: UUID


@dataclass(frozen=True, slots=True)
class DecisionId:
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


@dataclass(frozen=True, slots=True)
class InvocationId:
    value: UUID
