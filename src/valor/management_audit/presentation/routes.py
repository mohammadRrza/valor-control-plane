from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from valor.management_audit.application.query import (
    ListManagementAuditRecordsHandler,
    ListManagementAuditRecordsQuery,
    ManagementAuditReaderPort,
    TenantAuditNotFound,
)
from valor.management_audit.presentation.schemas import ManagementAuditRecordResponse
from valor.security.application.authorization import authorize_tenant
from valor.security.application.errors import TenantManagementAccessDenied
from valor.security.application.principal import AuthenticatedPrincipal
from valor.security.presentation.authentication import require_management_principal


def audit_reader(request: Request) -> ManagementAuditReaderPort:
    return cast(ManagementAuditReaderPort, request.app.state.management_audit_reader)


router = APIRouter(prefix="/tenants", tags=["management-audit"])


@router.get("/{tenant_id}/audit-records", response_model=list[ManagementAuditRecordResponse])
async def list_audit_records(
    tenant_id: UUID,
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
    reader: Annotated[ManagementAuditReaderPort, Depends(audit_reader)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ManagementAuditRecordResponse]:
    try:
        authorize_tenant(principal, tenant_id)
    except TenantManagementAccessDenied as error:
        raise TenantAuditNotFound from error
    records = await ListManagementAuditRecordsHandler(reader)(
        ListManagementAuditRecordsQuery(tenant_id, start, end, limit)
    )
    return [ManagementAuditRecordResponse.from_domain(record) for record in records]
