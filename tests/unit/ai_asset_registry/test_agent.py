from datetime import UTC, datetime
from uuid import UUID

import pytest

from valor.ai_asset_registry.domain.agent import Agent, AgentId, AgentName
from valor.ai_asset_registry.domain.errors import InvalidAgentName
from valor.ai_asset_registry.domain.ownership import OwningTenantId

AGENT_ID = AgentId(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
TENANT_ID = OwningTenantId(UUID("11111111-1111-4111-8111-111111111111"))
REGISTERED_AT = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)


def test_agent_registration_preserves_tenant_identity_and_canonicalizes_name() -> None:
    agent = Agent.register(AGENT_ID, TENANT_ID, "  Support   Agent ", REGISTERED_AT)
    assert agent.id == AGENT_ID
    assert agent.tenant_id == TENANT_ID
    assert agent.name.value == "Support Agent"
    assert agent.name.normalized == "support agent"
    assert agent.created_at == REGISTERED_AT


@pytest.mark.parametrize("name", ["", " ", "\t\n"])
def test_agent_name_rejects_empty_content(name: str) -> None:
    with pytest.raises(InvalidAgentName, match="must not be empty"):
        AgentName(name)


def test_agent_name_rejects_more_than_one_hundred_canonical_characters() -> None:
    with pytest.raises(InvalidAgentName, match="at most 100"):
        AgentName("a" * 101)


def test_agent_requires_timezone_aware_registration_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Agent.register(AGENT_ID, TENANT_ID, "Support Agent", datetime(2026, 2, 3))
