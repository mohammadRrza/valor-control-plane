"""Runtime admission and model-provider ports."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from valor.runtime_gateway.domain.identity import (
    AgentId,
    InvocationId,
    ModelId,
    PolicyDecisionId,
    TenantId,
)
from valor.runtime_gateway.domain.usage import InvocationUsage


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
    usage: InvocationUsage | None = None
    provider_response_id: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimePolicyDecision:
    id: PolicyDecisionId
    effect: str
    permission_id: UUID | None


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


class RuntimePolicyDecisionPort(Protocol):
    async def decide(
        self,
        *,
        invocation_id: InvocationId,
        tenant_id: TenantId,
        agent_id: AgentId,
        model_id: ModelId,
    ) -> RuntimePolicyDecision: ...


class RuntimeUsageReaderPort(Protocol):
    async def consumed_total_units(
        self,
        *,
        runtime_principal_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> int: ...


class ProviderTransportError(Exception):
    """Sanitized infrastructure-to-application provider failure signal."""
