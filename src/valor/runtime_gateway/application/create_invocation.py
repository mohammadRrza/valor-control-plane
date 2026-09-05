"""CreateInvocation command orchestration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from valor.runtime_gateway.application.errors import (
    AgentNotAvailable,
    InvocationCostLimited,
    InvocationDenied,
    InvocationUsageLimited,
    ModelNotAvailable,
    ProviderInvocationFailed,
    ProviderNotSupportedForRuntime,
    TenantCostBudgetConfigurationUnavailable,
    TenantNotAvailable,
)
from valor.runtime_gateway.application.ports import (
    AgentRuntimeLookupPort,
    InvocationPricingPort,
    ModelProviderPort,
    ModelRuntimeLookupPort,
    ProviderTransportError,
    RuntimePolicyDecisionPort,
    RuntimeUsageReaderPort,
    TenantCostBudgetPort,
    TenantEstimatedCostReaderPort,
    TenantRuntimeLookupPort,
)
from valor.runtime_gateway.application.unit_of_work import InvocationUnitOfWork
from valor.runtime_gateway.domain.cost import attribute_cost
from valor.runtime_gateway.domain.cost_budget import decide_tenant_cost_budget
from valor.runtime_gateway.domain.identity import AgentId, InvocationId, ModelId, TenantId
from valor.runtime_gateway.domain.invocation import Invocation, validated_input
from valor.runtime_gateway.domain.usage_limit import decide_usage_limit, utc_day_window


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CreateInvocationCommand:
    runtime_principal_id: str
    tenant_id: TenantId
    agent_id: AgentId
    model_id: ModelId
    input_text: str
    usage_limit: int
    per_invocation_allowance: int


class CreateInvocationHandler:
    def __init__(
        self,
        unit_of_work: InvocationUnitOfWork,
        tenants: TenantRuntimeLookupPort,
        agents: AgentRuntimeLookupPort,
        models: ModelRuntimeLookupPort,
        openai_provider: ModelProviderPort,
        policy: RuntimePolicyDecisionPort,
        usage_reader: RuntimeUsageReaderPort,
        pricing: InvocationPricingPort,
        tenant_budgets: TenantCostBudgetPort,
        tenant_cost_reader: TenantEstimatedCostReaderPort,
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
        self._usage_reader = usage_reader
        self._pricing = pricing
        self._tenant_budgets = tenant_budgets
        self._tenant_cost_reader = tenant_cost_reader
        self._id_factory = id_factory
        self._clock = clock

    async def __call__(self, command: CreateInvocationCommand) -> Invocation:
        started_at = self._clock()
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
        window = utc_day_window(started_at)
        consumed = await self._usage_reader.consumed_total_units(
            runtime_principal_id=command.runtime_principal_id,
            window_start=window.start,
            window_end=window.end,
        )
        usage_decision = decide_usage_limit(
            consumed_units=consumed,
            limit_units=command.usage_limit,
            allowance_units=command.per_invocation_allowance,
            window=window,
        )
        if not usage_decision.allowed:
            limited = Invocation.limited(
                invocation_id,
                command.tenant_id,
                command.agent_id,
                command.model_id,
                input_text,
                started_at,
                self._clock(),
                decision.id,
                command.runtime_principal_id,
                consumed_units=usage_decision.consumed_units,
                limit_units=usage_decision.limit_units,
                allowance_units=usage_decision.allowance_units,
                window_start=usage_decision.window.start,
                window_end=usage_decision.window.end,
            )
            await self._persist(limited)
            raise InvocationUsageLimited(invocation_id, window.end)
        budget = self._tenant_budgets.resolve(command.tenant_id)
        if budget is None:
            raise TenantCostBudgetConfigurationUnavailable
        attributed_cost = await self._tenant_cost_reader.attributed_cost(
            tenant_id=command.tenant_id,
            window_start=window.start,
            window_end=window.end,
        )
        budget_decision = decide_tenant_cost_budget(
            attributed_cost=attributed_cost,
            budget=budget,
            window=window,
        )
        if not budget_decision.allowed:
            cost_limited = Invocation.cost_limited(
                invocation_id,
                command.tenant_id,
                command.agent_id,
                command.model_id,
                input_text,
                started_at,
                self._clock(),
                decision.id,
                command.runtime_principal_id,
                consumed=budget_decision.attributed_cost,
                limit=budget_decision.budget,
                allowance=budget_decision.allowance,
                window_start=window.start,
                window_end=window.end,
            )
            await self._persist(cost_limited)
            raise InvocationCostLimited(invocation_id, window.end)
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

        pricing = self._pricing.resolve(
            provider=model.provider,
            provider_model_reference=model.provider_model_reference,
        )
        cost = attribute_cost(result.usage, pricing)
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
            result.usage,
            result.provider_response_id,
            cost,
        )
        await self._persist(succeeded)
        return succeeded

    async def _persist(self, invocation: Invocation) -> None:
        async with self._unit_of_work as unit_of_work:
            await unit_of_work.invocations.add(invocation)
            await unit_of_work.commit()
