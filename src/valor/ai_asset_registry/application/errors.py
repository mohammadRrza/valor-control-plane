"""Protocol-independent AI Asset Registry application failures."""

from valor.ai_asset_registry.domain.agent import AgentId
from valor.ai_asset_registry.domain.model import ModelId
from valor.ai_asset_registry.domain.ownership import OwningTenantId


class AgentNotFound(Exception):
    def __init__(self, agent_id: AgentId) -> None:
        super().__init__(f"Agent {agent_id.value} was not found.")
        self.agent_id = agent_id


class AgentNameAlreadyExists(Exception):
    """Raised when an Agent name is already registered for its tenant."""


class ModelNotFound(Exception):
    def __init__(self, model_id: ModelId) -> None:
        super().__init__(f"Model {model_id.value} was not found.")
        self.model_id = model_id


class ModelNameAlreadyExists(Exception):
    """Raised when a Model name is already registered for its tenant."""


class OwningTenantNotFound(Exception):
    def __init__(self, tenant_id: OwningTenantId) -> None:
        super().__init__(f"Owning tenant {tenant_id.value} was not found.")
        self.tenant_id = tenant_id
