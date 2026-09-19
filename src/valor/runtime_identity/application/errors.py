class RuntimeIdentityError(Exception):
    """Base expected Runtime identity failure."""


class RuntimePrincipalNotFound(RuntimeIdentityError):
    pass


class RuntimeCredentialNotFound(RuntimeIdentityError):
    pass


class RuntimeBindingNotFound(RuntimeIdentityError):
    pass


class InvalidRuntimeIdentityCommand(RuntimeIdentityError):
    pass


class RuntimePrincipalManagementDenied(RuntimeIdentityError):
    pass


class RuntimeUsageLimitsAlreadyInitialized(RuntimeIdentityError):
    pass


class RuntimeIdentityContinuityConflict(RuntimeIdentityError):
    pass
