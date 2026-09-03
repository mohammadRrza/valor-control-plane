"""Agent HTTP request and response contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from valor.ai_asset_registry.domain.agent import MAX_AGENT_NAME_LENGTH, Agent


class RegisterAgentRequest(BaseModel):
    tenant_id: UUID
    name: str = Field(min_length=1, max_length=MAX_AGENT_NAME_LENGTH)


class AgentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    created_at: datetime

    @classmethod
    def from_domain(cls, agent: Agent) -> "AgentResponse":
        return cls(
            id=agent.id.value,
            tenant_id=agent.tenant_id.value,
            name=agent.name.value,
            created_at=agent.created_at,
        )
