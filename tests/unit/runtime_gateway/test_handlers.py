from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from valor.runtime_gateway.application.create_invocation import (
    CreateInvocationCommand,
    CreateInvocationHandler,
)
from valor.runtime_gateway.application.errors import (
    AgentNotAvailable,
    InvocationDenied,
    InvocationNotFound,
    ModelNotAvailable,
    ProviderInvocationFailed,
    ProviderNotSupportedForRuntime,
    TenantNotAvailable,
)
from valor.runtime_gateway.application.get_invocation import (
    GetInvocationHandler,
    GetInvocationQuery,
)
from valor.runtime_gateway.application.ports import (
    AgentRuntimeIdentity,
    ModelRuntimeReference,
    ProviderInvocationResult,
    ProviderTransportError,
    RuntimePolicyDecision,
)
from valor.runtime_gateway.domain.identity import (
    AgentId,
    InvocationId,
    ModelId,
    PolicyDecisionId,
    TenantId,
)
from valor.runtime_gateway.domain.invocation import Invocation, InvocationStatus

INVOCATION_UUID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
TENANT_ID = TenantId(UUID("11111111-1111-4111-8111-111111111111"))
OTHER_TENANT_ID = TenantId(UUID("22222222-2222-4222-8222-222222222222"))
AGENT_ID = AgentId(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
MODEL_ID = ModelId(UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"))
STARTED_AT = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)
COMPLETED_AT = STARTED_AT + timedelta(seconds=1)
DECISION_ID = PolicyDecisionId(UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"))


class InMemoryInvocationRepository:
    def __init__(self) -> None:
        self.items: dict[InvocationId, Invocation] = {}

    async def add(self, invocation: Invocation) -> None:
        self.items[invocation.id] = invocation

    async def get(self, invocation_id: InvocationId) -> Invocation | None:
        return self.items.get(invocation_id)


class RecordingInvocationUnitOfWork:
    def __init__(self, repository: InMemoryInvocationRepository | None = None) -> None:
        self._repository = repository or InMemoryInvocationRepository()
        self.commits = 0
        self.entered = 0

    @property
    def invocations(self) -> InMemoryInvocationRepository:
        return self._repository

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


class AdmissionStub:
    def __init__(
        self,
        *,
        tenant_exists: bool = True,
        agent: AgentRuntimeIdentity | None = None,
        model: ModelRuntimeReference | None = None,
    ) -> None:
        self.tenant_exists = tenant_exists
        self.agent: AgentRuntimeIdentity | None = (
            agent if agent is not None else AgentRuntimeIdentity(AGENT_ID, TENANT_ID)
        )
        self.model: ModelRuntimeReference | None = (
            model
            if model is not None
            else ModelRuntimeReference(MODEL_ID, TENANT_ID, "openai", "gpt-test")
        )

    async def exists(self, tenant_id: TenantId) -> bool:
        del tenant_id
        return self.tenant_exists

    async def get_agent(self, agent_id: AgentId) -> AgentRuntimeIdentity | None:
        del agent_id
        return self.agent

    async def get_model(self, model_id: ModelId) -> ModelRuntimeReference | None:
        del model_id
        return self.model


class ProviderStub:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.calls: list[tuple[str, str]] = []

    async def invoke(self, *, model_reference: str, input_text: str) -> ProviderInvocationResult:
        self.calls.append((model_reference, input_text))
        if self.fails:
            raise ProviderTransportError
        return ProviderInvocationResult("deterministic output")


class PolicyStub:
    def __init__(self, effect: str = "allow") -> None:
        self.effect = effect
        self.calls = 0

    async def decide(
        self,
        *,
        invocation_id: InvocationId,
        tenant_id: TenantId,
        agent_id: AgentId,
        model_id: ModelId,
    ) -> RuntimePolicyDecision:
        del invocation_id, tenant_id, agent_id, model_id
        self.calls += 1
        return RuntimePolicyDecision(DECISION_ID, self.effect, None)


def handler(
    unit_of_work: RecordingInvocationUnitOfWork,
    admission: AdmissionStub,
    provider: ProviderStub,
    policy: PolicyStub | None = None,
) -> CreateInvocationHandler:
    times = iter((STARTED_AT, COMPLETED_AT))
    return CreateInvocationHandler(
        unit_of_work,
        admission,
        admission,
        admission,
        provider,
        policy or PolicyStub(),
        id_factory=lambda: INVOCATION_UUID,
        clock=lambda: next(times),
    )


def command() -> CreateInvocationCommand:
    return CreateInvocationCommand(TENANT_ID, AGENT_ID, MODEL_ID, " explain zero trust ")


@pytest.mark.asyncio
async def test_valid_admission_invokes_provider_and_commits_succeeded_invocation() -> None:
    unit_of_work = RecordingInvocationUnitOfWork()
    provider = ProviderStub()
    result = await handler(unit_of_work, AdmissionStub(), provider)(command())
    assert result.id == InvocationId(INVOCATION_UUID)
    assert result.status is InvocationStatus.SUCCEEDED
    assert result.output_text == "deterministic output"
    assert (result.started_at, result.completed_at) == (STARTED_AT, COMPLETED_AT)
    assert provider.calls == [("gpt-test", "explain zero trust")]
    assert unit_of_work.commits == 1
    assert unit_of_work.entered == 1


@pytest.mark.asyncio
async def test_missing_tenant_is_rejected_before_provider_or_uow() -> None:
    unit_of_work = RecordingInvocationUnitOfWork()
    provider = ProviderStub()
    with pytest.raises(TenantNotAvailable):
        await handler(unit_of_work, AdmissionStub(tenant_exists=False), provider)(command())
    assert provider.calls == []
    assert unit_of_work.entered == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent", "error"),
    [
        (None, AgentNotAvailable),
        (AgentRuntimeIdentity(AGENT_ID, OTHER_TENANT_ID), AgentNotAvailable),
    ],
)
async def test_missing_or_cross_tenant_agent_is_rejected(
    agent: AgentRuntimeIdentity | None, error: type[Exception]
) -> None:
    admission = AdmissionStub()
    admission.agent = agent
    with pytest.raises(error):
        await handler(RecordingInvocationUnitOfWork(), admission, ProviderStub())(command())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "error"),
    [
        (None, ModelNotAvailable),
        (
            ModelRuntimeReference(MODEL_ID, OTHER_TENANT_ID, "openai", "gpt-test"),
            ModelNotAvailable,
        ),
    ],
)
async def test_missing_or_cross_tenant_model_is_rejected(
    model: ModelRuntimeReference | None, error: type[Exception]
) -> None:
    admission = AdmissionStub()
    admission.model = model
    with pytest.raises(error):
        await handler(RecordingInvocationUnitOfWork(), admission, ProviderStub())(command())


@pytest.mark.asyncio
async def test_unsupported_provider_is_rejected_without_invocation() -> None:
    admission = AdmissionStub(
        model=ModelRuntimeReference(MODEL_ID, TENANT_ID, "anthropic", "claude-test")
    )
    unit_of_work = RecordingInvocationUnitOfWork()
    with pytest.raises(ProviderNotSupportedForRuntime):
        await handler(unit_of_work, admission, ProviderStub())(command())
    assert unit_of_work.entered == 0


@pytest.mark.asyncio
async def test_provider_failure_is_recorded_then_translated() -> None:
    unit_of_work = RecordingInvocationUnitOfWork()
    with pytest.raises(ProviderInvocationFailed) as error:
        await handler(unit_of_work, AdmissionStub(), ProviderStub(fails=True))(command())
    invocation_id = InvocationId(INVOCATION_UUID)
    assert error.value.invocation_id == invocation_id
    assert unit_of_work.invocations.items[invocation_id].status is InvocationStatus.FAILED
    assert unit_of_work.invocations.items[invocation_id].output_text is None
    assert unit_of_work.commits == 1


@pytest.mark.asyncio
async def test_get_invocation_returns_record_without_commit() -> None:
    repository = InMemoryInvocationRepository()
    invocation = Invocation.failed(
        InvocationId(INVOCATION_UUID),
        TENANT_ID,
        AGENT_ID,
        MODEL_ID,
        "input",
        STARTED_AT,
        COMPLETED_AT,
        DECISION_ID,
    )
    await repository.add(invocation)
    unit_of_work = RecordingInvocationUnitOfWork(repository)
    result = await GetInvocationHandler(unit_of_work)(GetInvocationQuery(invocation.id))
    assert result == invocation
    assert unit_of_work.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("effect", ["deny", "default-deny"])
async def test_policy_deny_records_denied_invocation_without_provider(effect: str) -> None:
    unit_of_work = RecordingInvocationUnitOfWork()
    provider = ProviderStub()
    policy = PolicyStub(effect)
    with pytest.raises(InvocationDenied) as error:
        await handler(unit_of_work, AdmissionStub(), provider, policy)(command())
    invocation = unit_of_work.invocations.items[InvocationId(INVOCATION_UUID)]
    assert invocation.status is InvocationStatus.DENIED
    assert invocation.policy_decision_id == DECISION_ID
    assert error.value.decision_id == DECISION_ID
    assert provider.calls == []
    assert unit_of_work.commits == 1


@pytest.mark.asyncio
async def test_get_invocation_raises_when_missing() -> None:
    invocation_id = InvocationId(INVOCATION_UUID)
    with pytest.raises(InvocationNotFound):
        await GetInvocationHandler(RecordingInvocationUnitOfWork())(
            GetInvocationQuery(invocation_id)
        )
