"""Protocol-independent Runtime Gateway application failures."""

from datetime import datetime

from valor.runtime_gateway.domain.identity import (
    AgentId,
    InvocationId,
    ModelId,
    PolicyDecisionId,
    TenantId,
)


class TenantNotAvailable(Exception):
    def __init__(self, tenant_id: TenantId) -> None:
        super().__init__(f"Tenant {tenant_id.value} is not available for this invocation.")
        self.tenant_id = tenant_id


class AgentNotAvailable(Exception):
    def __init__(self, agent_id: AgentId) -> None:
        super().__init__(f"Agent {agent_id.value} is not available for this invocation.")
        self.agent_id = agent_id


class ModelNotAvailable(Exception):
    def __init__(self, model_id: ModelId) -> None:
        super().__init__(f"Model {model_id.value} is not available for this invocation.")
        self.model_id = model_id


class ProviderNotSupportedForRuntime(Exception):
    def __init__(self, provider: str) -> None:
        super().__init__(f"Provider {provider!r} is not supported for runtime invocation.")
        self.provider = provider


class ProviderInvocationFailed(Exception):
    def __init__(self, invocation_id: InvocationId) -> None:
        super().__init__(f"Provider invocation failed for {invocation_id.value}.")
        self.invocation_id = invocation_id


class InvocationNotFound(Exception):
    def __init__(self, invocation_id: InvocationId) -> None:
        super().__init__(f"Invocation {invocation_id.value} was not found.")
        self.invocation_id = invocation_id


class InvocationDenied(Exception):
    def __init__(self, invocation_id: InvocationId, decision_id: PolicyDecisionId) -> None:
        self.invocation_id = invocation_id
        self.decision_id = decision_id


class InvocationUsageLimited(Exception):
    def __init__(self, invocation_id: InvocationId, window_end: datetime) -> None:
        self.invocation_id = invocation_id
        self.window_end = window_end


class UsageLimitUnavailable(Exception):
    """The usage ledger could not be read safely."""


class TenantCostBudgetConfigurationUnavailable(Exception):
    """No explicit Tenant monetary governance configuration is available."""


class TenantCostBudgetCheckUnavailable(Exception):
    """The persisted Tenant cost ledger could not be read safely."""


class InvocationCostLimited(Exception):
    def __init__(self, invocation_id: InvocationId, window_end: datetime) -> None:
        self.invocation_id = invocation_id
        self.window_end = window_end
