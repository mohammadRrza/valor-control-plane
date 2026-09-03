"""Persistence port for the governed Model aggregate."""

from typing import Protocol

from valor.ai_asset_registry.domain.model import Model, ModelId


class ModelRepository(Protocol):
    async def add(self, model: Model) -> None: ...

    async def get(self, model_id: ModelId) -> Model | None: ...
