from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from valor.policy_risk.application.unit_of_work import PolicyUnitOfWork
from valor.policy_risk.domain.identity import (
    AgentId,
    DecisionId,
    InvocationId,
    ModelId,
    TenantId,
)
from valor.policy_risk.domain.policy import PolicyDecision, PolicyEffect


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class EvaluateRuntimePermissionCommand:
    invocation_id: InvocationId
    tenant_id: TenantId
    agent_id: AgentId
    model_id: ModelId


class EvaluateRuntimePermissionHandler:
    def __init__(
        self,
        unit_of_work: PolicyUnitOfWork,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._uow = unit_of_work
        self._id_factory = id_factory
        self._clock = clock

    async def __call__(self, command: EvaluateRuntimePermissionCommand) -> PolicyDecision:
        async with self._uow as uow:
            permission = await uow.permissions.get_effective(
                command.tenant_id, command.agent_id, command.model_id
            )
            decision = PolicyDecision(
                DecisionId(self._id_factory()),
                command.invocation_id,
                command.tenant_id,
                command.agent_id,
                command.model_id,
                permission.id if permission is not None else None,
                permission.effect if permission is not None else PolicyEffect.DENY,
                self._clock(),
            )
            await uow.decisions.add(decision)
            await uow.commit()
        return decision
