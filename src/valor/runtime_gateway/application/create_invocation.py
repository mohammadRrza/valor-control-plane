"""CreateInvocation command orchestration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from valor.runtime_gateway.application.errors import (
    AgentNotAvailable,
    InvocationDenied,
    ModelNotAvailable,
    ProviderInvocationFailed,
    ProviderNotSupportedForRuntime,
    TenantNotAvailable,
)
from valor.runtime_gateway.application.ports import (
    AgentRuntimeLookupPort,
    ModelProviderPort,
    ModelRuntimeLookupPort,
    ProviderTransportError,
    RuntimePolicyDecisionPort,
    TenantRuntimeLookupPort,
)
from valor.runtime_gateway.application.unit_of_work import InvocationUnitOfWork
from valor.runtime_gateway.domain.identity import AgentId, InvocationId, ModelId, TenantId
from valor.runtime_gateway.domain.invocation import Invocation, validated_input


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CreateInvocationCommand:
    runtime_principal_id: str
    tenant_id: TenantId
    agent_id: AgentId
    model_id: ModelId
    input_text: str


class CreateInvocationHandler:
    def __init__(
        self,
        unit_of_work: InvocationUnitOfWork,
        tenants: TenantRuntimeLookupPort,
        agents: AgentRuntimeLookupPort,
        models: ModelRuntimeLookupPort,
        openai_provider: ModelProviderPort,
        policy: RuntimePolicyDecisionPort,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._tenants = tenants
        self._agents = agents
        self._models = models
        self._openai_provider = openai_provider
        self._policy = policy
        self._id_factory = id_factory
        self._clock = clock

    async def __call__(self, command: CreateInvocationCommand) -> Invocation:
        input_text = validated_input(command.input_text)
        if not await self._tenants.exists(command.tenant_id):
            raise TenantNotAvailable(command.tenant_id)
        agent = await self._agents.get_agent(command.agent_id)
        if agent is None or agent.tenant_id != command.tenant_id:
            raise AgentNotAvailable(command.agent_id)
        model = await self._models.get_model(command.model_id)
        if model is None or model.tenant_id != command.tenant_id:
            raise ModelNotAvailable(command.model_id)
        if model.provider != "openai":
            raise ProviderNotSupportedForRuntime(model.provider)

        invocation_id = InvocationId(self._id_factory())
        started_at = self._clock()
        decision = await self._policy.decide(
            invocation_id=invocation_id,
            tenant_id=command.tenant_id,
            agent_id=command.agent_id,
            model_id=command.model_id,
        )
        if decision.effect != "allow":
            denied = Invocation.denied(
                invocation_id,
                command.tenant_id,
                command.agent_id,
                command.model_id,
                input_text,
                started_at,
                self._clock(),
                decision.id,
                command.runtime_principal_id,
            )
            await self._persist(denied)
            raise InvocationDenied(invocation_id, decision.id)
        try:
            result = await self._openai_provider.invoke(
                model_reference=model.provider_model_reference,
                input_text=input_text,
            )
        except ProviderTransportError:
            failed = Invocation.failed(
                invocation_id,
                command.tenant_id,
                command.agent_id,
                command.model_id,
                input_text,
                started_at,
                self._clock(),
                decision.id,
                command.runtime_principal_id,
            )
            await self._persist(failed)
            raise ProviderInvocationFailed(invocation_id) from None

        succeeded = Invocation.succeeded(
            invocation_id,
            command.tenant_id,
            command.agent_id,
            command.model_id,
            input_text,
            result.output_text,
            started_at,
            self._clock(),
            decision.id,
            command.runtime_principal_id,
        )
        await self._persist(succeeded)
        return succeeded

    async def _persist(self, invocation: Invocation) -> None:
        async with self._unit_of_work as unit_of_work:
            await unit_of_work.invocations.add(invocation)
            await unit_of_work.commit()
