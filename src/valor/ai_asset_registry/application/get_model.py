"""GetModel query and handler."""

from dataclasses import dataclass

from valor.ai_asset_registry.application.errors import ModelNotFound
from valor.ai_asset_registry.application.model_unit_of_work import ModelUnitOfWork
from valor.ai_asset_registry.domain.model import Model, ModelId


@dataclass(frozen=True, slots=True)
class GetModelQuery:
    model_id: ModelId


class GetModelHandler:
    def __init__(self, unit_of_work: ModelUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def __call__(self, query: GetModelQuery) -> Model:
        async with self._unit_of_work as unit_of_work:
            model = await unit_of_work.models.get(query.model_id)
        if model is None:
            raise ModelNotFound(query.model_id)
        return model
