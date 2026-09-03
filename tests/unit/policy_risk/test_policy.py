from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from valor.policy_risk.domain.identity import (
    AgentId,
    DecisionId,
    InvocationId,
    ModelId,
    PermissionId,
    TenantId,
)
from valor.policy_risk.domain.policy import AgentModelPermission, PolicyDecision, PolicyEffect

NOW = datetime(2026, 3, 4, 5, 6, tzinfo=UTC)
TENANT = TenantId(UUID("11111111-1111-4111-8111-111111111111"))
AGENT = AgentId(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
MODEL = ModelId(UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"))
PERMISSION = PermissionId(UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"))


@pytest.mark.parametrize("effect", list(PolicyEffect))
def test_permission_represents_one_explicit_effect(effect: PolicyEffect) -> None:
    permission = AgentModelPermission(PERMISSION, TENANT, AGENT, MODEL, effect, NOW, NOW)
    assert permission.effect is effect
    assert permission.id == PERMISSION


def test_default_deny_decision_has_no_synthetic_permission() -> None:
    decision = PolicyDecision(
        DecisionId(UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")),
        InvocationId(UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")),
        TENANT,
        AGENT,
        MODEL,
        None,
        PolicyEffect.DENY,
        NOW,
    )
    assert decision.effect is PolicyEffect.DENY
    assert decision.permission_id is None


def test_explicit_decision_references_permission() -> None:
    decision = PolicyDecision(
        DecisionId(UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")),
        InvocationId(UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")),
        TENANT,
        AGENT,
        MODEL,
        PERMISSION,
        PolicyEffect.ALLOW,
        NOW,
    )
    assert decision.permission_id == PERMISSION


def test_policy_timestamps_are_aware_and_ordered() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AgentModelPermission(
            PERMISSION, TENANT, AGENT, MODEL, PolicyEffect.ALLOW, datetime(2026, 1, 1), NOW
        )
    with pytest.raises(ValueError, match="cannot precede"):
        AgentModelPermission(
            PERMISSION, TENANT, AGENT, MODEL, PolicyEffect.ALLOW, NOW, NOW - timedelta(seconds=1)
        )
