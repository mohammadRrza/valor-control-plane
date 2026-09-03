"""AI Asset Registry domain failures."""


class InvalidAgentName(ValueError):
    """Raised when an Agent name violates domain invariants."""


class InvalidModelName(ValueError):
    """Raised when a governed Model name violates domain invariants."""


class InvalidProviderModelReference(ValueError):
    """Raised when an external provider model reference is invalid."""
