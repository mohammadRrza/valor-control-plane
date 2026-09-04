"""Invocation aggregate for one completed synchronous runtime request."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from valor.runtime_gateway.domain.cost import InvocationCost
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
    LIMITED = "limited"


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
    usage_consumed_units: int | None = None
    usage_limit_units: int | None = None
    usage_allowance_units: int | None = None
    usage_window_start: datetime | None = None
    usage_window_end: datetime | None = None
    estimated_cost: InvocationCost | None = None

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
            raise InvalidInvocationOutput(
                "A failed, denied, or limited Invocation must not retain output."
            )
        evidence = (
            self.usage_consumed_units,
            self.usage_limit_units,
            self.usage_allowance_units,
            self.usage_window_start,
            self.usage_window_end,
        )
        if self.status is InvocationStatus.LIMITED:
            if (
                self.usage_consumed_units is None
                or self.usage_limit_units is None
                or self.usage_allowance_units is None
                or self.usage_window_start is None
                or self.usage_window_end is None
            ):
                raise ValueError("A limited Invocation requires usage-limit evidence.")
            if self.usage is not None or self.provider_response_id is not None:
                raise ValueError("A limited Invocation cannot contain provider telemetry.")
            if (
                self.usage_consumed_units < 0
                or self.usage_limit_units <= 0
                or self.usage_allowance_units <= 0
                or self.usage_allowance_units > self.usage_limit_units
                or self.usage_consumed_units + self.usage_allowance_units <= self.usage_limit_units
            ):
                raise ValueError("Limited Invocation usage evidence is inconsistent.")
            for timestamp in (self.usage_window_start, self.usage_window_end):
                if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                    raise ValueError("Usage-limit window must be timezone-aware.")
            if self.usage_window_end <= self.usage_window_start:
                raise ValueError("Usage-limit window end must follow its start.")
        elif any(value is not None for value in evidence):
            raise ValueError("Usage-limit evidence belongs only to a limited Invocation.")
        if self.estimated_cost is not None:
            if self.status is not InvocationStatus.SUCCEEDED:
                raise ValueError("Estimated cost belongs only to a succeeded Invocation.")
            if (
                self.usage is None
                or self.usage.input_units is None
                or self.usage.output_units is None
            ):
                raise ValueError("Estimated cost requires input and output usage.")

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
        estimated_cost: InvocationCost | None = None,
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
            None,
            None,
            None,
            None,
            None,
            estimated_cost,
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

    @classmethod
    def limited(
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
        *,
        consumed_units: int,
        limit_units: int,
        allowance_units: int,
        window_start: datetime,
        window_end: datetime,
    ) -> "Invocation":
        return cls(
            invocation_id,
            tenant_id,
            agent_id,
            model_id,
            InvocationStatus.LIMITED,
            input_text,
            None,
            started_at,
            completed_at,
            policy_decision_id,
            runtime_principal_id,
            _duration_ms(started_at, completed_at),
            None,
            None,
            consumed_units,
            limit_units,
            allowance_units,
            window_start,
            window_end,
        )


def _duration_ms(started_at: datetime, completed_at: datetime) -> int:
    for timestamp in (started_at, completed_at):
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Invocation timestamps must be timezone-aware.")
    if completed_at < started_at:
        raise ValueError("Invocation completion cannot precede its start.")
    delta = completed_at - started_at
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000
