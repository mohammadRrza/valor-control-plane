"""Persistence port for the Agent aggregate."""

from typing import Protocol

from valor.ai_asset_registry.domain.agent import Agent, AgentId


class AgentRepository(Protocol):
    async def add(self, agent: Agent) -> None: ...

    async def get(self, agent_id: AgentId) -> Agent | None: ...
