from dataclasses import dataclass
from typing import Protocol

from valor.policy_risk.domain.identity import AgentId, ModelId, TenantId


@dataclass(frozen=True, slots=True)
class PolicyAgentIdentity:
    id: AgentId
    tenant_id: TenantId


@dataclass(frozen=True, slots=True)
class PolicyModelIdentity:
    id: ModelId
    tenant_id: TenantId


class PolicyTenantLookupPort(Protocol):
    async def tenant_exists(self, tenant_id: TenantId) -> bool: ...


class PolicyAgentLookupPort(Protocol):
    async def get_agent(self, agent_id: AgentId) -> PolicyAgentIdentity | None: ...


class PolicyModelLookupPort(Protocol):
    async def get_model(self, model_id: ModelId) -> PolicyModelIdentity | None: ...
