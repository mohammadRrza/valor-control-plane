"""Versioned Tenant HTTP routes."""

from collections.abc import Callable
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from valor.identity_tenancy.application.create_tenant import (
    CreateTenantCommand,
    CreateTenantHandler,
)
from valor.identity_tenancy.application.get_tenant import GetTenantHandler, GetTenantQuery
from valor.identity_tenancy.application.unit_of_work import TenantUnitOfWork
from valor.identity_tenancy.domain.tenant import TenantId
from valor.identity_tenancy.presentation.schemas import CreateTenantRequest, TenantResponse

TenantUnitOfWorkFactory = Callable[[], TenantUnitOfWork]


def tenant_unit_of_work(request: Request) -> TenantUnitOfWork:
    factory = cast(TenantUnitOfWorkFactory, request.app.state.tenant_unit_of_work_factory)
    return factory()


router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: CreateTenantRequest,
    response: Response,
    unit_of_work: Annotated[TenantUnitOfWork, Depends(tenant_unit_of_work)],
) -> TenantResponse:
    tenant = await CreateTenantHandler(unit_of_work)(CreateTenantCommand(name=payload.name))
    response.headers["Location"] = f"/api/v1/tenants/{tenant.id.value}"
    return TenantResponse.from_domain(tenant)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    unit_of_work: Annotated[TenantUnitOfWork, Depends(tenant_unit_of_work)],
) -> TenantResponse:
    tenant = await GetTenantHandler(unit_of_work)(GetTenantQuery(TenantId(tenant_id)))
    return TenantResponse.from_domain(tenant)
