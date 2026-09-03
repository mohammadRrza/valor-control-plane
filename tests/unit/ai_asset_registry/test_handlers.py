from datetime import UTC, datetime
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from valor.ai_asset_registry.application.errors import AgentNotFound, OwningTenantNotFound
from valor.ai_asset_registry.application.get_agent import GetAgentHandler, GetAgentQuery
from valor.ai_asset_registry.application.register_agent import (
    RegisterAgentCommand,
    RegisterAgentHandler,
)
from valor.ai_asset_registry.domain.agent import Agent, AgentId
from valor.ai_asset_registry.domain.ownership import OwningTenantId

AGENT_UUID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_ID = OwningTenantId(UUID("11111111-1111-4111-8111-111111111111"))
REGISTERED_AT = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)


class InMemoryAgentRepository:
    def __init__(self) -> None:
        self.agents: dict[AgentId, Agent] = {}

    async def add(self, agent: Agent) -> None:
        self.agents[agent.id] = agent

    async def get(self, agent_id: AgentId) -> Agent | None:
        return self.agents.get(agent_id)


class RecordingAgentUnitOfWork:
    def __init__(self, agents: InMemoryAgentRepository | None = None) -> None:
        self._agents = agents or InMemoryAgentRepository()
        self.commits = 0
        self.entered = 0

    @property
    def agents(self) -> InMemoryAgentRepository:
        return self._agents

    async def __aenter__(self) -> Self:
        self.entered += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


class TenantExistenceStub:
    def __init__(self, exists: bool) -> None:
        self._exists = exists

    async def exists(self, tenant_id: OwningTenantId) -> bool:
        del tenant_id
        return self._exists


@pytest.mark.asyncio
async def test_register_agent_for_existing_tenant_commits() -> None:
    unit_of_work = RecordingAgentUnitOfWork()
    handler = RegisterAgentHandler(
        unit_of_work,
        TenantExistenceStub(True),
        id_factory=lambda: AGENT_UUID,
        clock=lambda: REGISTERED_AT,
    )
    agent = await handler(RegisterAgentCommand(TENANT_ID, " Support  Agent "))
    assert agent.id == AgentId(AGENT_UUID)
    assert agent.tenant_id == TENANT_ID
    assert agent.name.value == "Support Agent"
    assert agent.created_at == REGISTERED_AT
    assert unit_of_work.commits == 1


@pytest.mark.asyncio
async def test_register_agent_rejects_unknown_tenant_without_opening_write_uow() -> None:
    unit_of_work = RecordingAgentUnitOfWork()
    handler = RegisterAgentHandler(unit_of_work, TenantExistenceStub(False))
    with pytest.raises(OwningTenantNotFound) as error:
        await handler(RegisterAgentCommand(TENANT_ID, "Support Agent"))
    assert error.value.tenant_id == TENANT_ID
    assert unit_of_work.entered == 0
    assert unit_of_work.commits == 0


@pytest.mark.asyncio
async def test_get_agent_returns_existing_agent_without_commit() -> None:
    agent = Agent.register(AgentId(AGENT_UUID), TENANT_ID, "Support Agent", REGISTERED_AT)
    repository = InMemoryAgentRepository()
    await repository.add(agent)
    unit_of_work = RecordingAgentUnitOfWork(repository)
    result = await GetAgentHandler(unit_of_work)(GetAgentQuery(agent.id))
    assert result == agent
    assert unit_of_work.commits == 0


@pytest.mark.asyncio
async def test_get_agent_raises_application_error_when_missing() -> None:
    agent_id = AgentId(AGENT_UUID)
    with pytest.raises(AgentNotFound) as error:
        await GetAgentHandler(RecordingAgentUnitOfWork())(GetAgentQuery(agent_id))
    assert error.value.agent_id == agent_id
