class ManagementPrincipalNotFound(Exception):
    pass


class ManagementCredentialNotFound(Exception):
    pass


class PrincipalManagementDenied(Exception):
    pass


class InvalidManagementIdentityCommand(Exception):
    pass


class LastPrincipalManagerConflict(Exception):
    pass


class BootstrapAuthenticationFailed(Exception):
    pass


class BootstrapAlreadyCompleted(Exception):
    pass
