from typing import Protocol

from valor.policy_risk.domain.identity import AgentId, ModelId, PermissionId, TenantId
from valor.policy_risk.domain.policy import AgentModelPermission, PolicyDecision


class AgentModelPermissionRepository(Protocol):
    async def set(self, permission: AgentModelPermission) -> AgentModelPermission: ...

    async def get(self, permission_id: PermissionId) -> AgentModelPermission | None: ...

    async def get_effective(
        self, tenant_id: TenantId, agent_id: AgentId, model_id: ModelId
    ) -> AgentModelPermission | None: ...


class PolicyDecisionRepository(Protocol):
    async def add(self, decision: PolicyDecision) -> None: ...
