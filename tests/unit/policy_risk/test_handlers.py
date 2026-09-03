from datetime import UTC, datetime
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from valor.policy_risk.application.errors import (
    PolicyAgentNotAvailable,
    PolicyModelNotAvailable,
    PolicyTenantNotAvailable,
)
from valor.policy_risk.application.evaluate_permission import (
    EvaluateRuntimePermissionCommand,
    EvaluateRuntimePermissionHandler,
)
from valor.policy_risk.application.ports import PolicyAgentIdentity, PolicyModelIdentity
from valor.policy_risk.application.set_permission import (
    SetAgentModelPermissionCommand,
    SetAgentModelPermissionHandler,
)
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
OTHER = TenantId(UUID("22222222-2222-4222-8222-222222222222"))
AGENT = AgentId(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
MODEL = ModelId(UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"))
PERMISSION_UUID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
DECISION_UUID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
INVOCATION = InvocationId(UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"))


class PermissionRepo:
    def __init__(self) -> None:
        self.permission: AgentModelPermission | None = None

    async def set(self, permission: AgentModelPermission) -> AgentModelPermission:
        self.permission = permission
        return permission

    async def get(self, permission_id: PermissionId) -> AgentModelPermission | None:
        return self.permission if self.permission and self.permission.id == permission_id else None

    async def get_effective(
        self, tenant_id: TenantId, agent_id: AgentId, model_id: ModelId
    ) -> AgentModelPermission | None:
        del tenant_id, agent_id, model_id
        return self.permission


class DecisionRepo:
    def __init__(self) -> None:
        self.items: list[PolicyDecision] = []

    async def add(self, decision: PolicyDecision) -> None:
        self.items.append(decision)


class Uow:
    def __init__(self) -> None:
        self.permissions = PermissionRepo()
        self.decisions = DecisionRepo()
        self.commits = 0
        self.entered = 0

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


class Admission:
    def __init__(self) -> None:
        self.tenant = True
        self.agent: PolicyAgentIdentity | None = PolicyAgentIdentity(AGENT, TENANT)
        self.model: PolicyModelIdentity | None = PolicyModelIdentity(MODEL, TENANT)

    async def tenant_exists(self, tenant_id: TenantId) -> bool:
        del tenant_id
        return self.tenant

    async def get_agent(self, agent_id: AgentId) -> PolicyAgentIdentity | None:
        del agent_id
        return self.agent

    async def get_model(self, model_id: ModelId) -> PolicyModelIdentity | None:
        del model_id
        return self.model


@pytest.mark.asyncio
async def test_set_same_tenant_permission_commits() -> None:
    uow, admission = Uow(), Admission()
    result = await SetAgentModelPermissionHandler(
        uow,
        admission,
        admission,
        admission,
        id_factory=lambda: PERMISSION_UUID,
        clock=lambda: NOW,
    )(SetAgentModelPermissionCommand(TENANT, AGENT, MODEL, PolicyEffect.ALLOW))
    assert result.effect is PolicyEffect.ALLOW
    assert uow.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["tenant", "agent", "model"])
async def test_invalid_or_cross_tenant_resources_do_not_commit(failure: str) -> None:
    uow, admission = Uow(), Admission()
    expected: type[Exception]
    if failure == "tenant":
        admission.tenant = False
        expected = PolicyTenantNotAvailable
    elif failure == "agent":
        admission.agent = PolicyAgentIdentity(AGENT, OTHER)
        expected = PolicyAgentNotAvailable
    else:
        admission.model = PolicyModelIdentity(MODEL, OTHER)
        expected = PolicyModelNotAvailable
    with pytest.raises(expected):
        await SetAgentModelPermissionHandler(uow, admission, admission, admission)(
            SetAgentModelPermissionCommand(TENANT, AGENT, MODEL, PolicyEffect.ALLOW)
        )
    assert uow.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("permission_effect", [None, PolicyEffect.DENY, PolicyEffect.ALLOW])
async def test_evaluation_persists_default_deny_or_explicit_effect(
    permission_effect: PolicyEffect | None,
) -> None:
    uow = Uow()
    if permission_effect is not None:
        uow.permissions.permission = AgentModelPermission(
            PermissionId(PERMISSION_UUID), TENANT, AGENT, MODEL, permission_effect, NOW, NOW
        )
    decision = await EvaluateRuntimePermissionHandler(
        uow, id_factory=lambda: DECISION_UUID, clock=lambda: NOW
    )(EvaluateRuntimePermissionCommand(INVOCATION, TENANT, AGENT, MODEL))
    assert decision.effect is (permission_effect or PolicyEffect.DENY)
    assert decision.permission_id == (PermissionId(PERMISSION_UUID) if permission_effect else None)
    assert decision.id == DecisionId(DECISION_UUID)
    assert uow.commits == 1
