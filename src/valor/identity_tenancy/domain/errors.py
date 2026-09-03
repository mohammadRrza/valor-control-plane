"""Identity and Tenancy domain failures."""


class InvalidTenantName(ValueError):
    """Raised when a tenant name violates domain invariants."""
