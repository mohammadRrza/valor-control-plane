from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from valor.policy_risk.domain.policy import AgentModelPermission, PolicyEffect


class SetAgentModelPermissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    agent_id: UUID
    model_id: UUID
    effect: PolicyEffect


class AgentModelPermissionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    agent_id: UUID
    model_id: UUID
    effect: PolicyEffect
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, permission: AgentModelPermission) -> "AgentModelPermissionResponse":
        return cls(
            id=permission.id.value,
            tenant_id=permission.tenant_id.value,
            agent_id=permission.agent_id.value,
            model_id=permission.model_id.value,
            effect=permission.effect,
            created_at=permission.created_at,
            updated_at=permission.updated_at,
        )
