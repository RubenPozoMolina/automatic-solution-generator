class SolutionGenerationError(RuntimeError):
    """Raised when the solution generation pipeline cannot continue."""


class SessionTimeoutError(SolutionGenerationError):
    """Raised when an agent session does not become idle within the configured time."""
