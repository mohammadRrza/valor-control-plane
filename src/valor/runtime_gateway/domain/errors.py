"""Runtime Gateway domain failures."""


class InvalidInvocationInput(ValueError):
    """Raised when text input cannot form an Invocation."""


class InvalidInvocationOutput(ValueError):
    """Raised when provider output cannot form a succeeded Invocation."""
