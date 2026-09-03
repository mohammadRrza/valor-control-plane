"""Persistence port for the Tenant aggregate."""

from typing import Protocol

from valor.identity_tenancy.domain.tenant import Tenant, TenantId


class TenantRepository(Protocol):
    async def add(self, tenant: Tenant) -> None: ...

    async def get(self, tenant_id: TenantId) -> Tenant | None: ...
