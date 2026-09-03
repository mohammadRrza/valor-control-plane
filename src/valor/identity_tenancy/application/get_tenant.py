"""GetTenant query and handler."""

from dataclasses import dataclass

from valor.identity_tenancy.application.errors import TenantNotFound
from valor.identity_tenancy.application.unit_of_work import TenantUnitOfWork
from valor.identity_tenancy.domain.tenant import Tenant, TenantId


@dataclass(frozen=True, slots=True)
class GetTenantQuery:
    tenant_id: TenantId


class GetTenantHandler:
    def __init__(self, unit_of_work: TenantUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def __call__(self, query: GetTenantQuery) -> Tenant:
        async with self._unit_of_work as unit_of_work:
            tenant = await unit_of_work.tenants.get(query.tenant_id)
        if tenant is None:
            raise TenantNotFound(query.tenant_id)
        return tenant
