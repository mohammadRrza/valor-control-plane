"""Exact Tenant daily estimated-cost budget decision semantics."""

from dataclasses import dataclass
from decimal import Decimal

from valor.runtime_gateway.domain.usage_limit import UsageWindow


@dataclass(frozen=True, slots=True)
class TenantCostBudget:
    limit: Decimal
    allowance: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.currency != "USD":
            raise ValueError("Only USD Tenant cost budgets are supported.")
        if self.limit <= 0 or self.allowance <= 0 or self.allowance > self.limit:
            raise ValueError("Tenant cost budget configuration is invalid.")


@dataclass(frozen=True, slots=True)
class TenantCostBudgetDecision:
    allowed: bool
    attributed_cost: Decimal
    budget: Decimal
    allowance: Decimal
    window: UsageWindow


def decide_tenant_cost_budget(
    *, attributed_cost: Decimal, budget: TenantCostBudget, window: UsageWindow
) -> TenantCostBudgetDecision:
    if attributed_cost < 0:
        raise ValueError("Attributed Tenant cost must not be negative.")
    return TenantCostBudgetDecision(
        attributed_cost + budget.allowance <= budget.limit,
        attributed_cost,
        budget.limit,
        budget.allowance,
        window,
    )
