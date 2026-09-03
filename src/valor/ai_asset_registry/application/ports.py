"""Narrow cross-context contracts required by Agent use cases."""

from typing import Protocol

from valor.ai_asset_registry.domain.ownership import OwningTenantId


class TenantExistencePort(Protocol):
    async def exists(self, tenant_id: OwningTenantId) -> bool: ...
