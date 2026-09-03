"""RegisterAgent command and handler."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from valor.ai_asset_registry.application.errors import OwningTenantNotFound
from valor.ai_asset_registry.application.ports import TenantExistencePort
from valor.ai_asset_registry.application.unit_of_work import AgentUnitOfWork
from valor.ai_asset_registry.domain.agent import Agent, AgentId, OwningTenantId


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RegisterAgentCommand:
    tenant_id: OwningTenantId
    name: str


class RegisterAgentHandler:
    def __init__(
        self,
        unit_of_work: AgentUnitOfWork,
        tenant_existence: TenantExistencePort,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._tenant_existence = tenant_existence
        self._id_factory = id_factory
        self._clock = clock

    async def __call__(self, command: RegisterAgentCommand) -> Agent:
        agent = Agent.register(
            agent_id=AgentId(self._id_factory()),
            tenant_id=command.tenant_id,
            name=command.name,
            created_at=self._clock(),
        )
        if not await self._tenant_existence.exists(command.tenant_id):
            raise OwningTenantNotFound(command.tenant_id)
        async with self._unit_of_work as unit_of_work:
            await unit_of_work.agents.add(agent)
            await unit_of_work.commit()
        return agent
