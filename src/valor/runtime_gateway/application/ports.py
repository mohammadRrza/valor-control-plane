"""Runtime admission and model-provider ports."""

from dataclasses import dataclass
from typing import Protocol

from valor.runtime_gateway.domain.identity import AgentId, ModelId, TenantId


@dataclass(frozen=True, slots=True)
class AgentRuntimeIdentity:
    id: AgentId
    tenant_id: TenantId


@dataclass(frozen=True, slots=True)
class ModelRuntimeReference:
    id: ModelId
    tenant_id: TenantId
    provider: str
    provider_model_reference: str


@dataclass(frozen=True, slots=True)
class ProviderInvocationResult:
    output_text: str


class TenantRuntimeLookupPort(Protocol):
    async def exists(self, tenant_id: TenantId) -> bool: ...


class AgentRuntimeLookupPort(Protocol):
    async def get_agent(self, agent_id: AgentId) -> AgentRuntimeIdentity | None: ...


class ModelRuntimeLookupPort(Protocol):
    async def get_model(self, model_id: ModelId) -> ModelRuntimeReference | None: ...


class ModelProviderPort(Protocol):
    async def invoke(
        self, *, model_reference: str, input_text: str
    ) -> ProviderInvocationResult: ...


class ProviderTransportError(Exception):
    """Sanitized infrastructure-to-application provider failure signal."""
