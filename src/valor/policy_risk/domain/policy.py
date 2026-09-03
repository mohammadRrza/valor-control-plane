"""Explicit Agent-to-Model permission and evaluated decision."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from valor.policy_risk.domain.identity import (
    AgentId,
    DecisionId,
    InvocationId,
    ModelId,
    PermissionId,
    TenantId,
)


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


def ensure_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Policy timestamps must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class AgentModelPermission:
    id: PermissionId
    tenant_id: TenantId
    agent_id: AgentId
    model_id: ModelId
    effect: PolicyEffect
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        ensure_aware(self.created_at)
        ensure_aware(self.updated_at)
        if self.updated_at < self.created_at:
            raise ValueError("Permission update cannot precede creation.")


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    id: DecisionId
    invocation_id: InvocationId
    tenant_id: TenantId
    agent_id: AgentId
    model_id: ModelId
    permission_id: PermissionId | None
    effect: PolicyEffect
    decided_at: datetime

    def __post_init__(self) -> None:
        ensure_aware(self.decided_at)
