from datetime import UTC, datetime
from uuid import UUID

import pytest

from valor.ai_asset_registry.domain.errors import (
    InvalidModelName,
    InvalidProviderModelReference,
)
from valor.ai_asset_registry.domain.model import (
    Model,
    ModelId,
    ModelName,
    Provider,
    ProviderModelReference,
)
from valor.ai_asset_registry.domain.ownership import OwningTenantId

MODEL_ID = ModelId(UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"))
TENANT_ID = OwningTenantId(UUID("11111111-1111-4111-8111-111111111111"))
REGISTERED_AT = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)


def test_model_registration_canonicalizes_governed_identity() -> None:
    model = Model.register(
        MODEL_ID, TENANT_ID, " Support  Model ", Provider.OPENAI, " gpt-5.2 ", REGISTERED_AT
    )
    assert model.id == MODEL_ID
    assert model.tenant_id == TENANT_ID
    assert model.name.value == "Support Model"
    assert model.name.normalized == "support model"
    assert model.provider is Provider.OPENAI
    assert model.provider_model_reference.value == "gpt-5.2"
    assert model.created_at == REGISTERED_AT


@pytest.mark.parametrize("name", ["", " ", "\t\n"])
def test_model_name_rejects_empty_content(name: str) -> None:
    with pytest.raises(InvalidModelName, match="must not be empty"):
        ModelName(name)


def test_model_name_rejects_more_than_one_hundred_canonical_characters() -> None:
    with pytest.raises(InvalidModelName, match="at most 100"):
        ModelName("a" * 101)


@pytest.mark.parametrize("reference", ["", " ", "\t\n"])
def test_provider_reference_rejects_empty_content(reference: str) -> None:
    with pytest.raises(InvalidProviderModelReference, match="must not be empty"):
        ProviderModelReference(reference)


def test_provider_reference_rejects_more_than_255_characters() -> None:
    with pytest.raises(InvalidProviderModelReference, match="at most 255"):
        ProviderModelReference("a" * 256)


def test_model_requires_timezone_aware_registration_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Model.register(
            MODEL_ID,
            TENANT_ID,
            "Support Model",
            Provider.OPENAI,
            "gpt-5.2",
            datetime(2026, 2, 3),
        )
