"""Exact configured pricing and Invocation cost attribution values."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from valor.runtime_gateway.domain.usage import InvocationUsage

COST_QUANTUM = Decimal("0.000000000001")


@dataclass(frozen=True, slots=True)
class PricingSnapshot:
    provider: str
    provider_model_reference: str
    version: str
    basis_units: int
    input_rate: Decimal
    output_rate: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.provider_model_reference.strip():
            raise ValueError("Pricing provider and model reference must not be empty.")
        if not self.version.strip() or len(self.version) > 255:
            raise ValueError("Pricing version must be between 1 and 255 characters.")
        if self.currency != "USD":
            raise ValueError("Only USD pricing is supported.")
        if self.basis_units <= 0 or self.input_rate < 0 or self.output_rate < 0:
            raise ValueError("Pricing basis must be positive and rates non-negative.")


@dataclass(frozen=True, slots=True)
class InvocationCost:
    currency: str
    input_cost: Decimal
    output_cost: Decimal
    total_cost: Decimal
    pricing_version: str
    pricing_basis_units: int
    pricing_input_rate: Decimal
    pricing_output_rate: Decimal

    def __post_init__(self) -> None:
        if self.currency != "USD":
            raise ValueError("Only USD cost attribution is supported.")
        if min(self.input_cost, self.output_cost, self.total_cost) < 0:
            raise ValueError("Attributed costs must not be negative.")
        if self.total_cost != self.input_cost + self.output_cost:
            raise ValueError("Attributed total cost must equal its components.")


def attribute_cost(
    usage: InvocationUsage | None, pricing: PricingSnapshot | None
) -> InvocationCost | None:
    if usage is None or usage.input_units is None or usage.output_units is None or pricing is None:
        return None
    with localcontext() as context:
        context.prec = 50
        input_cost = (
            Decimal(usage.input_units) * pricing.input_rate / pricing.basis_units
        ).quantize(COST_QUANTUM, rounding=ROUND_HALF_EVEN)
        output_cost = (
            Decimal(usage.output_units) * pricing.output_rate / pricing.basis_units
        ).quantize(COST_QUANTUM, rounding=ROUND_HALF_EVEN)
    return InvocationCost(
        pricing.currency,
        input_cost,
        output_cost,
        input_cost + output_cost,
        pricing.version,
        pricing.basis_units,
        pricing.input_rate,
        pricing.output_rate,
    )
