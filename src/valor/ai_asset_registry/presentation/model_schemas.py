"""HTTP contracts for governed Model references."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from valor.ai_asset_registry.domain.model import (
    MAX_MODEL_NAME_LENGTH,
    MAX_PROVIDER_MODEL_REFERENCE_LENGTH,
    Model,
    Provider,
)


class RegisterModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    name: str = Field(min_length=1, max_length=MAX_MODEL_NAME_LENGTH)
    provider: Provider
    provider_model_reference: str = Field(
        min_length=1, max_length=MAX_PROVIDER_MODEL_REFERENCE_LENGTH
    )


class ModelResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    provider: Provider
    provider_model_reference: str
    created_at: datetime

    @classmethod
    def from_domain(cls, model: Model) -> "ModelResponse":
        return cls(
            id=model.id.value,
            tenant_id=model.tenant_id.value,
            name=model.name.value,
            provider=model.provider,
            provider_model_reference=model.provider_model_reference.value,
            created_at=model.created_at,
        )
