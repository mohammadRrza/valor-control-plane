"""HTTP contracts for runtime Invocations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from valor.runtime_gateway.domain.invocation import MAX_INVOCATION_INPUT_LENGTH, Invocation
from valor.runtime_gateway.domain.usage import InvocationUsage


class CreateInvocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: UUID
    input: str = Field(min_length=1, max_length=MAX_INVOCATION_INPUT_LENGTH)


class InvocationUsageResponse(BaseModel):
    input_units: int | None
    output_units: int | None
    total_units: int | None

    @classmethod
    def from_domain(cls, usage: InvocationUsage) -> "InvocationUsageResponse":
        return cls(
            input_units=usage.input_units,
            output_units=usage.output_units,
            total_units=usage.total_units,
        )


class InvocationResponse(BaseModel):
    invocation_id: UUID
    tenant_id: UUID
    agent_id: UUID
    model_id: UUID
    status: str
    input: str
    output: str | None
    started_at: datetime
    completed_at: datetime
    policy_decision_id: UUID
    runtime_principal_id: str
    duration_ms: int | None
    usage: InvocationUsageResponse | None
    provider_response_id: str | None

    @classmethod
    def from_domain(cls, invocation: Invocation) -> "InvocationResponse":
        return cls(
            invocation_id=invocation.id.value,
            tenant_id=invocation.tenant_id.value,
            agent_id=invocation.agent_id.value,
            model_id=invocation.model_id.value,
            status=invocation.status.value,
            input=invocation.input_text,
            output=invocation.output_text,
            started_at=invocation.started_at,
            completed_at=invocation.completed_at,
            policy_decision_id=invocation.policy_decision_id.value,
            runtime_principal_id=invocation.runtime_principal_id,
            duration_ms=invocation.duration_ms,
            usage=(
                InvocationUsageResponse.from_domain(invocation.usage) if invocation.usage else None
            ),
            provider_response_id=invocation.provider_response_id,
        )
