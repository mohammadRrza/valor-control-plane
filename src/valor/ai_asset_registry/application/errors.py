"""Protocol-independent AI Asset Registry application failures."""

from valor.ai_asset_registry.domain.agent import AgentId, OwningTenantId


class AgentNotFound(Exception):
    def __init__(self, agent_id: AgentId) -> None:
        super().__init__(f"Agent {agent_id.value} was not found.")
        self.agent_id = agent_id


class AgentNameAlreadyExists(Exception):
    """Raised when an Agent name is already registered for its tenant."""


class OwningTenantNotFound(Exception):
    def __init__(self, tenant_id: OwningTenantId) -> None:
        super().__init__(f"Owning tenant {tenant_id.value} was not found.")
        self.tenant_id = tenant_id
