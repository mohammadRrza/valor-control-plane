from collections.abc import Callable

from valor.policy_risk.application.evaluate_permission import (
    EvaluateRuntimePermissionCommand,
    EvaluateRuntimePermissionHandler,
)
from valor.policy_risk.application.unit_of_work import PolicyUnitOfWork
from valor.policy_risk.domain.identity import (
    AgentId as PolicyAgentId,
)
from valor.policy_risk.domain.identity import (
    InvocationId as PolicyInvocationId,
)
from valor.policy_risk.domain.identity import (
    ModelId as PolicyModelId,
)
from valor.policy_risk.domain.identity import (
    TenantId as PolicyTenantId,
)
from valor.runtime_gateway.application.ports import RuntimePolicyDecision
from valor.runtime_gateway.domain.identity import (
    AgentId,
    InvocationId,
    ModelId,
    PolicyDecisionId,
    TenantId,
)


class RuntimePolicyAdapter:
    def __init__(self, unit_of_work_factory: Callable[[], PolicyUnitOfWork]) -> None:
        self._uow_factory = unit_of_work_factory

    async def decide(
        self,
        *,
        invocation_id: InvocationId,
        tenant_id: TenantId,
        agent_id: AgentId,
        model_id: ModelId,
    ) -> RuntimePolicyDecision:
        decision = await EvaluateRuntimePermissionHandler(self._uow_factory())(
            EvaluateRuntimePermissionCommand(
                PolicyInvocationId(invocation_id.value),
                PolicyTenantId(tenant_id.value),
                PolicyAgentId(agent_id.value),
                PolicyModelId(model_id.value),
            )
        )
        return RuntimePolicyDecision(
            PolicyDecisionId(decision.id.value),
            decision.effect.value,
            decision.permission_id.value if decision.permission_id else None,
        )
