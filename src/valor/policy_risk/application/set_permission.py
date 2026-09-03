from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from valor.policy_risk.application.errors import (
    PolicyAgentNotAvailable,
    PolicyModelNotAvailable,
    PolicyTenantNotAvailable,
)
from valor.policy_risk.application.ports import (
    PolicyAgentLookupPort,
    PolicyModelLookupPort,
    PolicyTenantLookupPort,
)
from valor.policy_risk.application.unit_of_work import PolicyUnitOfWork
from valor.policy_risk.domain.identity import AgentId, ModelId, PermissionId, TenantId
from valor.policy_risk.domain.policy import AgentModelPermission, PolicyEffect


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class SetAgentModelPermissionCommand:
    tenant_id: TenantId
    agent_id: AgentId
    model_id: ModelId
    effect: PolicyEffect


class SetAgentModelPermissionHandler:
    def __init__(
        self,
        unit_of_work: PolicyUnitOfWork,
        tenants: PolicyTenantLookupPort,
        agents: PolicyAgentLookupPort,
        models: PolicyModelLookupPort,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._uow = unit_of_work
        self._tenants = tenants
        self._agents = agents
        self._models = models
        self._id_factory = id_factory
        self._clock = clock

    async def __call__(self, command: SetAgentModelPermissionCommand) -> AgentModelPermission:
        if not await self._tenants.tenant_exists(command.tenant_id):
            raise PolicyTenantNotAvailable(command.tenant_id)
        agent = await self._agents.get_agent(command.agent_id)
        if agent is None or agent.tenant_id != command.tenant_id:
            raise PolicyAgentNotAvailable(command.agent_id)
        model = await self._models.get_model(command.model_id)
        if model is None or model.tenant_id != command.tenant_id:
            raise PolicyModelNotAvailable(command.model_id)
        now = self._clock()
        proposed = AgentModelPermission(
            PermissionId(self._id_factory()),
            command.tenant_id,
            command.agent_id,
            command.model_id,
            command.effect,
            now,
            now,
        )
        async with self._uow as uow:
            effective = await uow.permissions.set(proposed)
            await uow.commit()
        return effective
