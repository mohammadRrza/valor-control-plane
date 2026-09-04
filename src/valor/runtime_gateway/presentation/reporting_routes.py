"""Management-plane Tenant Runtime reporting route."""

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from valor.runtime_gateway.application.reporting import (
    GetTenantRuntimeReportHandler,
    GetTenantRuntimeReportQuery,
    TenantRuntimeReportNotFound,
    TenantRuntimeReportReaderPort,
)
from valor.runtime_gateway.domain.identity import TenantId
from valor.runtime_gateway.presentation.reporting_schemas import TenantRuntimeReportResponse
from valor.security.application.authorization import authorize_tenant
from valor.security.application.errors import TenantManagementAccessDenied
from valor.security.application.principal import AuthenticatedPrincipal
from valor.security.presentation.authentication import require_management_principal


def runtime_report_reader(request: Request) -> TenantRuntimeReportReaderPort:
    return cast(TenantRuntimeReportReaderPort, request.app.state.runtime_report_reader)


router = APIRouter(prefix="/tenants", tags=["runtime-reporting"])


@router.get("/{tenant_id}/runtime-report", response_model=TenantRuntimeReportResponse)
async def get_tenant_runtime_report(
    tenant_id: UUID,
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
    reader: Annotated[TenantRuntimeReportReaderPort, Depends(runtime_report_reader)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
) -> TenantRuntimeReportResponse:
    try:
        authorize_tenant(principal, tenant_id)
    except TenantManagementAccessDenied as error:
        raise TenantRuntimeReportNotFound from error
    report = await GetTenantRuntimeReportHandler(reader)(
        GetTenantRuntimeReportQuery(TenantId(tenant_id), start, end)
    )
    return TenantRuntimeReportResponse.from_application(report)
