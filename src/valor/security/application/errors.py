"""Protocol-independent authentication failures."""


class ManagementAuthenticationFailed(Exception):
    """The request did not prove possession of the management credential."""


class TenantManagementAccessDenied(Exception):
    """The principal is outside the requested Tenant management boundary."""
