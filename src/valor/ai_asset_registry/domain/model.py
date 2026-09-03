"""Governed Model reference aggregate and value objects."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from valor.ai_asset_registry.domain.errors import (
    InvalidModelName,
    InvalidProviderModelReference,
)
from valor.ai_asset_registry.domain.ownership import OwningTenantId

MAX_MODEL_NAME_LENGTH = 100
MAX_PROVIDER_MODEL_REFERENCE_LENGTH = 255


@dataclass(frozen=True, slots=True)
class ModelId:
    """Stable VALOR identity, distinct from any provider model reference."""

    value: UUID


class Provider(StrEnum):
    """External model ecosystem identity; this implies no live integration."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ModelName:
    value: str
    normalized: str = field(init=False)

    def __post_init__(self) -> None:
        canonical = " ".join(self.value.split())
        if not canonical:
            raise InvalidModelName("Model name must not be empty.")
        if len(canonical) > MAX_MODEL_NAME_LENGTH:
            raise InvalidModelName(
                f"Model name must be at most {MAX_MODEL_NAME_LENGTH} characters."
            )
        object.__setattr__(self, "value", canonical)
        object.__setattr__(self, "normalized", canonical.casefold())


@dataclass(frozen=True, slots=True)
class ProviderModelReference:
    value: str

    def __post_init__(self) -> None:
        canonical = self.value.strip()
        if not canonical:
            raise InvalidProviderModelReference("Provider model reference must not be empty.")
        if len(canonical) > MAX_PROVIDER_MODEL_REFERENCE_LENGTH:
            raise InvalidProviderModelReference(
                "Provider model reference must be at most "
                f"{MAX_PROVIDER_MODEL_REFERENCE_LENGTH} characters."
            )
        object.__setattr__(self, "value", canonical)


@dataclass(frozen=True, slots=True)
class Model:
    """Tenant-owned VALOR reference to an external model capability."""

    id: ModelId
    tenant_id: OwningTenantId
    name: ModelName
    provider: Provider
    provider_model_reference: ProviderModelReference
    created_at: datetime

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("Model registration time must be timezone-aware.")

    @classmethod
    def register(
        cls,
        model_id: ModelId,
        tenant_id: OwningTenantId,
        name: str,
        provider: Provider,
        provider_model_reference: str,
        created_at: datetime,
    ) -> "Model":
        return cls(
            id=model_id,
            tenant_id=tenant_id,
            name=ModelName(name),
            provider=provider,
            provider_model_reference=ProviderModelReference(provider_model_reference),
            created_at=created_at,
        )
