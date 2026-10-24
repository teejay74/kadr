class IndexerNotConfiguredError(RuntimeError):
    """Raised when Prowlarr credentials are absent or rejected."""


class IndexerUnavailableError(RuntimeError):
    """Raised when Prowlarr or its indexers cannot complete a request."""
