"""GetAgent query and handler."""

from dataclasses import dataclass

from valor.ai_asset_registry.application.errors import AgentNotFound
from valor.ai_asset_registry.application.unit_of_work import AgentUnitOfWork
from valor.ai_asset_registry.domain.agent import Agent, AgentId


@dataclass(frozen=True, slots=True)
class GetAgentQuery:
    agent_id: AgentId


class GetAgentHandler:
    def __init__(self, unit_of_work: AgentUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def __call__(self, query: GetAgentQuery) -> Agent:
        async with self._unit_of_work as unit_of_work:
            agent = await unit_of_work.agents.get(query.agent_id)
        if agent is None:
            raise AgentNotFound(query.agent_id)
        return agent
