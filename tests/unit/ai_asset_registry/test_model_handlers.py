from datetime import UTC, datetime
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from valor.ai_asset_registry.application.errors import ModelNotFound, OwningTenantNotFound
from valor.ai_asset_registry.application.get_model import GetModelHandler, GetModelQuery
from valor.ai_asset_registry.application.register_model import (
    RegisterModelCommand,
    RegisterModelHandler,
)
from valor.ai_asset_registry.domain.model import Model, ModelId, Provider
from valor.ai_asset_registry.domain.ownership import OwningTenantId

MODEL_UUID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
TENANT_ID = OwningTenantId(UUID("11111111-1111-4111-8111-111111111111"))
REGISTERED_AT = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)


class InMemoryModelRepository:
    def __init__(self) -> None:
        self.models: dict[ModelId, Model] = {}

    async def add(self, model: Model) -> None:
        self.models[model.id] = model

    async def get(self, model_id: ModelId) -> Model | None:
        return self.models.get(model_id)


class RecordingModelUnitOfWork:
    def __init__(self, models: InMemoryModelRepository | None = None) -> None:
        self._models = models or InMemoryModelRepository()
        self.commits = 0
        self.entered = 0

    @property
    def models(self) -> InMemoryModelRepository:
        return self._models

    async def __aenter__(self) -> Self:
        self.entered += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


class TenantExistenceStub:
    def __init__(self, exists: bool) -> None:
        self._exists = exists

    async def exists(self, tenant_id: OwningTenantId) -> bool:
        del tenant_id
        return self._exists


@pytest.mark.asyncio
async def test_register_model_for_existing_tenant_commits() -> None:
    unit_of_work = RecordingModelUnitOfWork()
    handler = RegisterModelHandler(
        unit_of_work,
        TenantExistenceStub(True),
        id_factory=lambda: MODEL_UUID,
        clock=lambda: REGISTERED_AT,
    )
    model = await handler(
        RegisterModelCommand(TENANT_ID, " Support  Model ", Provider.OPENAI, " gpt-5.2 ")
    )
    assert model.id == ModelId(MODEL_UUID)
    assert model.tenant_id == TENANT_ID
    assert model.name.value == "Support Model"
    assert model.provider is Provider.OPENAI
    assert model.provider_model_reference.value == "gpt-5.2"
    assert model.created_at == REGISTERED_AT
    assert unit_of_work.commits == 1


@pytest.mark.asyncio
async def test_register_model_rejects_unknown_tenant_without_write_uow() -> None:
    unit_of_work = RecordingModelUnitOfWork()
    handler = RegisterModelHandler(unit_of_work, TenantExistenceStub(False))
    command = RegisterModelCommand(TENANT_ID, "Support Model", Provider.OPENAI, "gpt-5.2")
    with pytest.raises(OwningTenantNotFound) as error:
        await handler(command)
    assert error.value.tenant_id == TENANT_ID
    assert unit_of_work.entered == 0
    assert unit_of_work.commits == 0


@pytest.mark.asyncio
async def test_get_model_returns_existing_model_without_commit() -> None:
    model = Model.register(
        ModelId(MODEL_UUID), TENANT_ID, "Support Model", Provider.OPENAI, "gpt-5.2", REGISTERED_AT
    )
    repository = InMemoryModelRepository()
    await repository.add(model)
    unit_of_work = RecordingModelUnitOfWork(repository)
    result = await GetModelHandler(unit_of_work)(GetModelQuery(model.id))
    assert result == model
    assert unit_of_work.commits == 0


@pytest.mark.asyncio
async def test_get_model_raises_application_error_when_missing() -> None:
    model_id = ModelId(MODEL_UUID)
    with pytest.raises(ModelNotFound) as error:
        await GetModelHandler(RecordingModelUnitOfWork())(GetModelQuery(model_id))
    assert error.value.model_id == model_id
