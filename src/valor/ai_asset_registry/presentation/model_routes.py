"""Versioned governed Model HTTP routes."""

from collections.abc import Callable
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from valor.ai_asset_registry.application.get_model import GetModelHandler, GetModelQuery
from valor.ai_asset_registry.application.model_unit_of_work import ModelUnitOfWork
from valor.ai_asset_registry.application.ports import TenantExistencePort
from valor.ai_asset_registry.application.register_model import (
    RegisterModelCommand,
    RegisterModelHandler,
)
from valor.ai_asset_registry.domain.model import ModelId
from valor.ai_asset_registry.domain.ownership import OwningTenantId
from valor.ai_asset_registry.presentation.dependencies import tenant_existence
from valor.ai_asset_registry.presentation.model_schemas import (
    ModelResponse,
    RegisterModelRequest,
)

ModelUnitOfWorkFactory = Callable[[], ModelUnitOfWork]


def model_unit_of_work(request: Request) -> ModelUnitOfWork:
    factory = cast(ModelUnitOfWorkFactory, request.app.state.model_unit_of_work_factory)
    return factory()


router = APIRouter(prefix="/models", tags=["models"])


@router.post("", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def register_model(
    payload: RegisterModelRequest,
    response: Response,
    unit_of_work: Annotated[ModelUnitOfWork, Depends(model_unit_of_work)],
    owning_tenant: Annotated[TenantExistencePort, Depends(tenant_existence)],
) -> ModelResponse:
    command = RegisterModelCommand(
        tenant_id=OwningTenantId(payload.tenant_id),
        name=payload.name,
        provider=payload.provider,
        provider_model_reference=payload.provider_model_reference,
    )
    model = await RegisterModelHandler(unit_of_work, owning_tenant)(command)
    response.headers["Location"] = f"/api/v1/models/{model.id.value}"
    return ModelResponse.from_domain(model)


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: UUID,
    unit_of_work: Annotated[ModelUnitOfWork, Depends(model_unit_of_work)],
) -> ModelResponse:
    model = await GetModelHandler(unit_of_work)(GetModelQuery(ModelId(model_id)))
    return ModelResponse.from_domain(model)
