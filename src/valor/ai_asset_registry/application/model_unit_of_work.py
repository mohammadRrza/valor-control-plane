"""Model-capable Unit of Work application port."""

from typing import Protocol

from valor.ai_asset_registry.domain.model_repository import ModelRepository
from valor.application.unit_of_work import UnitOfWork


class ModelUnitOfWork(UnitOfWork, Protocol):
    @property
    def models(self) -> ModelRepository: ...
