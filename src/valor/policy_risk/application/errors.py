from valor.policy_risk.domain.identity import AgentId, ModelId, PermissionId, TenantId


class PolicyTenantNotAvailable(Exception):
    def __init__(self, tenant_id: TenantId) -> None:
        self.tenant_id = tenant_id


class PolicyAgentNotAvailable(Exception):
    def __init__(self, agent_id: AgentId) -> None:
        self.agent_id = agent_id


class PolicyModelNotAvailable(Exception):
    def __init__(self, model_id: ModelId) -> None:
        self.model_id = model_id


class PermissionNotFound(Exception):
    def __init__(self, permission_id: PermissionId) -> None:
        self.permission_id = permission_id
