from decimal import Decimal

import pytest

from valor.runtime_gateway.domain.cost import InvocationCost, PricingSnapshot, attribute_cost
from valor.runtime_gateway.domain.usage import InvocationUsage


def pricing(
    input_rate: str = "2", output_rate: str = "8", *, basis: int = 1_000_000
) -> PricingSnapshot:
    return PricingSnapshot(
        "openai", "gpt-test", "pricing-v1", basis, Decimal(input_rate), Decimal(output_rate)
    )


def test_exact_input_output_cost_calculation() -> None:
    cost = attribute_cost(InvocationUsage(250_000, 100_000, 350_000), pricing())
    assert cost is not None
    assert cost.input_cost == Decimal("0.500000000000")
    assert cost.output_cost == Decimal("0.800000000000")
    assert cost.total_cost == Decimal("1.300000000000")


@pytest.mark.parametrize("usage", [None, InvocationUsage(None, 1, 1), InvocationUsage(1, None, 1)])
def test_incomplete_usage_has_no_cost(usage: InvocationUsage | None) -> None:
    assert attribute_cost(usage, pricing()) is None


def test_missing_pricing_has_no_cost() -> None:
    assert attribute_cost(InvocationUsage(1, 1, 2), None) is None


def test_zero_usage_and_zero_rates_produce_exact_zero() -> None:
    cost = attribute_cost(InvocationUsage(0, 0, 0), pricing("0", "0"))
    assert cost is not None and cost.total_cost == Decimal("0E-12")


def test_rounding_is_half_even_at_twelve_decimal_places() -> None:
    cost = attribute_cost(InvocationUsage(1, 0, 1), pricing("0.000000000001", "0", basis=2))
    assert cost is not None and cost.input_cost == Decimal("0E-12")


def test_cost_rejects_inexact_component_total() -> None:
    with pytest.raises(ValueError, match="equal its components"):
        InvocationCost(
            "USD",
            Decimal("1"),
            Decimal("2"),
            Decimal("4"),
            "v1",
            1,
            Decimal("1"),
            Decimal("1"),
        )
