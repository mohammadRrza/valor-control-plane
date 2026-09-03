from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from valor.runtime_gateway.domain.errors import InvalidInvocationInput, InvalidInvocationOutput
from valor.runtime_gateway.domain.identity import (
    AgentId,
    InvocationId,
    ModelId,
    PolicyDecisionId,
    TenantId,
)
from valor.runtime_gateway.domain.invocation import Invocation, InvocationStatus

INVOCATION_ID = InvocationId(UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"))
TENANT_ID = TenantId(UUID("11111111-1111-4111-8111-111111111111"))
AGENT_ID = AgentId(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
MODEL_ID = ModelId(UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"))
STARTED_AT = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)
COMPLETED_AT = STARTED_AT + timedelta(seconds=1)
DECISION_ID = PolicyDecisionId(UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"))


def test_succeeded_invocation_has_valor_identity_and_final_output() -> None:
    invocation = Invocation.succeeded(
        INVOCATION_ID,
        TENANT_ID,
        AGENT_ID,
        MODEL_ID,
        " Explain zero trust. ",
        "Trust must be continuously verified.",
        STARTED_AT,
        COMPLETED_AT,
        DECISION_ID,
    )
    assert invocation.id == INVOCATION_ID
    assert invocation.status is InvocationStatus.SUCCEEDED
    assert invocation.input_text == "Explain zero trust."
    assert invocation.output_text == "Trust must be continuously verified."


def test_failed_invocation_has_no_provider_output() -> None:
    invocation = Invocation.failed(
        INVOCATION_ID,
        TENANT_ID,
        AGENT_ID,
        MODEL_ID,
        "Explain zero trust.",
        STARTED_AT,
        COMPLETED_AT,
        DECISION_ID,
    )
    assert invocation.status is InvocationStatus.FAILED
    assert invocation.output_text is None


@pytest.mark.parametrize("input_text", ["", " ", "\t\n"])
def test_invocation_rejects_empty_input(input_text: str) -> None:
    with pytest.raises(InvalidInvocationInput, match="must not be empty"):
        Invocation.failed(
            INVOCATION_ID,
            TENANT_ID,
            AGENT_ID,
            MODEL_ID,
            input_text,
            STARTED_AT,
            COMPLETED_AT,
            DECISION_ID,
        )


def test_invocation_rejects_oversized_input() -> None:
    with pytest.raises(InvalidInvocationInput, match="at most 10000"):
        Invocation.failed(
            INVOCATION_ID,
            TENANT_ID,
            AGENT_ID,
            MODEL_ID,
            "a" * 10_001,
            STARTED_AT,
            COMPLETED_AT,
            DECISION_ID,
        )


def test_succeeded_invocation_requires_output() -> None:
    with pytest.raises(InvalidInvocationOutput, match="requires text output"):
        Invocation.succeeded(
            INVOCATION_ID,
            TENANT_ID,
            AGENT_ID,
            MODEL_ID,
            "input",
            " ",
            STARTED_AT,
            COMPLETED_AT,
            DECISION_ID,
        )


def test_failed_invocation_rejects_output() -> None:
    with pytest.raises(InvalidInvocationOutput, match="must not retain"):
        Invocation(
            INVOCATION_ID,
            TENANT_ID,
            AGENT_ID,
            MODEL_ID,
            InvocationStatus.FAILED,
            "input",
            "unexpected",
            STARTED_AT,
            COMPLETED_AT,
            DECISION_ID,
        )


@pytest.mark.parametrize(
    ("started_at", "completed_at"),
    [
        (datetime(2026, 2, 3), COMPLETED_AT),
        (STARTED_AT, datetime(2026, 2, 3)),
    ],
)
def test_invocation_requires_timezone_aware_timestamps(
    started_at: datetime, completed_at: datetime
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Invocation.failed(
            INVOCATION_ID,
            TENANT_ID,
            AGENT_ID,
            MODEL_ID,
            "input",
            started_at,
            completed_at,
            DECISION_ID,
        )


def test_invocation_completion_cannot_precede_start() -> None:
    with pytest.raises(ValueError, match="cannot precede"):
        Invocation.failed(
            INVOCATION_ID,
            TENANT_ID,
            AGENT_ID,
            MODEL_ID,
            "input",
            COMPLETED_AT,
            STARTED_AT,
            DECISION_ID,
        )


def test_denied_invocation_has_decision_and_no_output() -> None:
    invocation = Invocation.denied(
        INVOCATION_ID, TENANT_ID, AGENT_ID, MODEL_ID, "input", STARTED_AT, COMPLETED_AT, DECISION_ID
    )
    assert invocation.status is InvocationStatus.DENIED
    assert invocation.output_text is None
    assert invocation.policy_decision_id == DECISION_ID
