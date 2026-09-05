"""HTTP response contracts for Tenant Runtime reporting."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from valor.runtime_gateway.application.reporting import TenantRuntimeReport


class InvocationCountsResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    denied: int
    limited: int


class UsageTotalsResponse(BaseModel):
    input_units: int
    output_units: int
    total_units: int
    provider_executed_invocations: int
    attributed_invocations: int
    unavailable_invocations: int


class EstimatedCostTotalsResponse(BaseModel):
    currency: str
    total: str
    attributed_invocations: int
    unavailable_invocations: int


class AgentCostBreakdownResponse(BaseModel):
    agent_id: UUID
    invocation_count: int
    total_units: int
    usage_attributed_invocations: int
    usage_unavailable_invocations: int
    estimated_cost_total: str
    cost_attributed_invocations: int
    cost_unavailable_invocations: int


class ModelCostBreakdownResponse(BaseModel):
    model_id: UUID
    invocation_count: int
    total_units: int
    usage_attributed_invocations: int
    usage_unavailable_invocations: int
    estimated_cost_total: str
    cost_attributed_invocations: int
    cost_unavailable_invocations: int


class TenantRuntimeReportResponse(BaseModel):
    tenant_id: UUID
    start: datetime
    end: datetime
    invocations: InvocationCountsResponse
    usage: UsageTotalsResponse
    estimated_cost: EstimatedCostTotalsResponse
    top_agents_by_estimated_cost: list[AgentCostBreakdownResponse]
    top_models_by_estimated_cost: list[ModelCostBreakdownResponse]
    agent_breakdown_truncated: bool
    model_breakdown_truncated: bool

    @classmethod
    def from_application(cls, report: TenantRuntimeReport) -> "TenantRuntimeReportResponse":
        return cls(
            tenant_id=report.tenant_id.value,
            start=report.start,
            end=report.end,
            invocations=InvocationCountsResponse(
                total=report.invocations.total,
                succeeded=report.invocations.succeeded,
                failed=report.invocations.failed,
                denied=report.invocations.denied,
                limited=report.invocations.limited,
            ),
            usage=UsageTotalsResponse(
                input_units=report.usage.input_units,
                output_units=report.usage.output_units,
                total_units=report.usage.total_units,
                provider_executed_invocations=report.usage.provider_executed_invocations,
                attributed_invocations=report.usage.attributed_invocations,
                unavailable_invocations=report.usage.unavailable_invocations,
            ),
            estimated_cost=EstimatedCostTotalsResponse(
                currency=report.estimated_cost.currency,
                total=f"{report.estimated_cost.total:.12f}",
                attributed_invocations=report.estimated_cost.attributed_invocations,
                unavailable_invocations=report.estimated_cost.unavailable_invocations,
            ),
            top_agents_by_estimated_cost=[
                AgentCostBreakdownResponse(
                    agent_id=row.agent_id,
                    invocation_count=row.invocation_count,
                    total_units=row.total_units,
                    usage_attributed_invocations=row.usage_attributed_invocations,
                    usage_unavailable_invocations=row.usage_unavailable_invocations,
                    estimated_cost_total=f"{row.estimated_cost_total:.12f}",
                    cost_attributed_invocations=row.cost_attributed_invocations,
                    cost_unavailable_invocations=row.cost_unavailable_invocations,
                )
                for row in report.top_agents_by_estimated_cost
            ],
            top_models_by_estimated_cost=[
                ModelCostBreakdownResponse(
                    model_id=row.model_id,
                    invocation_count=row.invocation_count,
                    total_units=row.total_units,
                    usage_attributed_invocations=row.usage_attributed_invocations,
                    usage_unavailable_invocations=row.usage_unavailable_invocations,
                    estimated_cost_total=f"{row.estimated_cost_total:.12f}",
                    cost_attributed_invocations=row.cost_attributed_invocations,
                    cost_unavailable_invocations=row.cost_unavailable_invocations,
                )
                for row in report.top_models_by_estimated_cost
            ],
            agent_breakdown_truncated=report.agent_breakdown_truncated,
            model_breakdown_truncated=report.model_breakdown_truncated,
        )
