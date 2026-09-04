"""Configuration-backed provider pricing resolution."""

from valor.bootstrap.settings import PricingSettings
from valor.runtime_gateway.domain.cost import PricingSnapshot


class ConfiguredInvocationPricing:
    def __init__(self, settings: PricingSettings) -> None:
        self._entries = {
            (entry.provider, entry.provider_model_reference): PricingSnapshot(
                entry.provider,
                entry.provider_model_reference,
                entry.pricing_version,
                entry.price_basis_units,
                entry.input_price_per_basis,
                entry.output_price_per_basis,
                entry.currency,
            )
            for entry in settings.entries
        }

    def resolve(self, *, provider: str, provider_model_reference: str) -> PricingSnapshot | None:
        return self._entries.get((provider, provider_model_reference))
