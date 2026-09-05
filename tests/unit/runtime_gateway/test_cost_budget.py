from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from valor.runtime_gateway.domain.cost_budget import (
    TenantCostBudget,
    decide_tenant_cost_budget,
)
from valor.runtime_gateway.domain.usage_limit import UsageWindow

WINDOW = UsageWindow(datetime(2026, 9, 5, tzinfo=UTC), datetime(2026, 9, 6, tzinfo=UTC))


@pytest.mark.parametrize(
    ("cost", "expected"),
    [
        ("0", True),
        ("9", True),
        ("9.000000000001", False),
        ("10", False),
        ("0.000000000001", True),
    ],
)
def test_exact_decimal_budget_boundary(cost: str, expected: bool) -> None:
    decision = decide_tenant_cost_budget(
        attributed_cost=Decimal(cost),
        budget=TenantCostBudget(Decimal("10"), Decimal("1")),
        window=WINDOW,
    )
    assert decision.allowed is expected
    assert decision.attributed_cost == Decimal(cost)
    assert decision.window == WINDOW


@pytest.mark.parametrize(
    ("limit", "allowance", "currency"),
    [
        ("0", "1", "USD"),
        ("-1", "1", "USD"),
        ("10", "0", "USD"),
        ("10", "-1", "USD"),
        ("10", "11", "USD"),
        ("10", "1", "EUR"),
    ],
)
def test_invalid_budget_is_rejected(limit: str, allowance: str, currency: str) -> None:
    with pytest.raises(ValueError):
        TenantCostBudget(Decimal(limit), Decimal(allowance), currency)


def test_negative_consumption_is_rejected() -> None:
    with pytest.raises(ValueError):
        decide_tenant_cost_budget(
            attributed_cost=Decimal("-0.000000000001"),
            budget=TenantCostBudget(Decimal("10"), Decimal("1")),
            window=UsageWindow(WINDOW.start, WINDOW.start + timedelta(days=1)),
        )
