"""Invocation aggregate for one completed synchronous runtime request."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from valor.runtime_gateway.domain.errors import InvalidInvocationInput, InvalidInvocationOutput
from valor.runtime_gateway.domain.identity import (
    AgentId,
    InvocationId,
    ModelId,
    PolicyDecisionId,
    TenantId,
)
from valor.runtime_gateway.domain.usage import InvocationUsage

MAX_INVOCATION_INPUT_LENGTH = 10_000
MAX_PROVIDER_RESPONSE_ID_LENGTH = 255


class InvocationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


def validated_input(value: str) -> str:
    canonical = value.strip()
    if not canonical:
        raise InvalidInvocationInput("Invocation input must not be empty.")
    if len(canonical) > MAX_INVOCATION_INPUT_LENGTH:
        raise InvalidInvocationInput(
            f"Invocation input must be at most {MAX_INVOCATION_INPUT_LENGTH} characters."
        )
    return canonical


@dataclass(frozen=True, slots=True)
class Invocation:
    id: InvocationId
    tenant_id: TenantId
    agent_id: AgentId
    model_id: ModelId
    status: InvocationStatus
    input_text: str
    output_text: str | None
    started_at: datetime
    completed_at: datetime
    policy_decision_id: PolicyDecisionId
    runtime_principal_id: str
    duration_ms: int | None = None
    usage: InvocationUsage | None = None
    provider_response_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_text", validated_input(self.input_text))
        if not self.runtime_principal_id.strip():
            raise ValueError("Invocation runtime principal identity must not be empty.")
        for timestamp in (self.started_at, self.completed_at):
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("Invocation timestamps must be timezone-aware.")
        if self.completed_at < self.started_at:
            raise ValueError("Invocation completion cannot precede its start.")
        if self.duration_ms is not None and (
            isinstance(self.duration_ms, bool)
            or not isinstance(self.duration_ms, int)
            or self.duration_ms < 0
        ):
            raise ValueError("Invocation duration must be a non-negative integer.")
        if self.provider_response_id is not None:
            provider_response_id = self.provider_response_id.strip()
            if (
                not provider_response_id
                or len(provider_response_id) > MAX_PROVIDER_RESPONSE_ID_LENGTH
            ):
                raise ValueError("Provider response identity must be between 1 and 255 characters.")
            object.__setattr__(self, "provider_response_id", provider_response_id)
        if self.status is InvocationStatus.SUCCEEDED:
            if self.output_text is None or not self.output_text.strip():
                raise InvalidInvocationOutput("A succeeded Invocation requires text output.")
        elif self.output_text is not None:
            raise InvalidInvocationOutput("A failed or denied Invocation must not retain output.")

    @classmethod
    def succeeded(
        cls,
        invocation_id: InvocationId,
        tenant_id: TenantId,
        agent_id: AgentId,
        model_id: ModelId,
        input_text: str,
        output_text: str,
        started_at: datetime,
        completed_at: datetime,
        policy_decision_id: PolicyDecisionId,
        runtime_principal_id: str,
        usage: InvocationUsage | None = None,
        provider_response_id: str | None = None,
    ) -> "Invocation":
        return cls(
            invocation_id,
            tenant_id,
            agent_id,
            model_id,
            InvocationStatus.SUCCEEDED,
            input_text,
            output_text,
            started_at,
            completed_at,
            policy_decision_id,
            runtime_principal_id,
            _duration_ms(started_at, completed_at),
            usage,
            provider_response_id,
        )

    @classmethod
    def failed(
        cls,
        invocation_id: InvocationId,
        tenant_id: TenantId,
        agent_id: AgentId,
        model_id: ModelId,
        input_text: str,
        started_at: datetime,
        completed_at: datetime,
        policy_decision_id: PolicyDecisionId,
        runtime_principal_id: str,
    ) -> "Invocation":
        return cls(
            invocation_id,
            tenant_id,
            agent_id,
            model_id,
            InvocationStatus.FAILED,
            input_text,
            None,
            started_at,
            completed_at,
            policy_decision_id,
            runtime_principal_id,
            _duration_ms(started_at, completed_at),
        )

    @classmethod
    def denied(
        cls,
        invocation_id: InvocationId,
        tenant_id: TenantId,
        agent_id: AgentId,
        model_id: ModelId,
        input_text: str,
        started_at: datetime,
        completed_at: datetime,
        policy_decision_id: PolicyDecisionId,
        runtime_principal_id: str,
    ) -> "Invocation":
        return cls(
            invocation_id,
            tenant_id,
            agent_id,
            model_id,
            InvocationStatus.DENIED,
            input_text,
            None,
            started_at,
            completed_at,
            policy_decision_id,
            runtime_principal_id,
            _duration_ms(started_at, completed_at),
        )


def _duration_ms(started_at: datetime, completed_at: datetime) -> int:
    for timestamp in (started_at, completed_at):
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Invocation timestamps must be timezone-aware.")
    if completed_at < started_at:
        raise ValueError("Invocation completion cannot precede its start.")
    delta = completed_at - started_at
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000
