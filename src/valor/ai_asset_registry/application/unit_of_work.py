"""Agent-capable Unit of Work application port."""

from typing import Protocol

from valor.ai_asset_registry.domain.repository import AgentRepository
from valor.application.unit_of_work import UnitOfWork


class AgentUnitOfWork(UnitOfWork, Protocol):
    @property
    def agents(self) -> AgentRepository: ...
