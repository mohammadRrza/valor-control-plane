"""Invocation aggregate for one completed synchronous runtime request."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from valor.runtime_gateway.domain.errors import InvalidInvocationInput, InvalidInvocationOutput
from valor.runtime_gateway.domain.identity import AgentId, InvocationId, ModelId, TenantId

MAX_INVOCATION_INPUT_LENGTH = 10_000


class InvocationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_text", validated_input(self.input_text))
        for timestamp in (self.started_at, self.completed_at):
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("Invocation timestamps must be timezone-aware.")
        if self.completed_at < self.started_at:
            raise ValueError("Invocation completion cannot precede its start.")
        if self.status is InvocationStatus.SUCCEEDED:
            if self.output_text is None or not self.output_text.strip():
                raise InvalidInvocationOutput("A succeeded Invocation requires text output.")
        elif self.output_text is not None:
            raise InvalidInvocationOutput("A failed Invocation must not retain provider output.")

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
        )
