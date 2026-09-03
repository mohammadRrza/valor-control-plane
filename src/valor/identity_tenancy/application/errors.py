"""Protocol-independent Identity and Tenancy application failures."""

from valor.identity_tenancy.domain.tenant import TenantId


class TenantNotFound(Exception):
    def __init__(self, tenant_id: TenantId) -> None:
        super().__init__(f"Tenant {tenant_id.value} was not found.")
        self.tenant_id = tenant_id


class TenantNameAlreadyExists(Exception):
    """Raised when a normalized tenant name is already registered."""
