class MetadataError(Exception):
    """Base metadata service error."""


class MetadataNotConfiguredError(MetadataError):
    """TMDB credentials are absent or rejected."""


class MetadataUnavailableError(MetadataError):
    """TMDB cannot provide a response right now."""


class MetadataNotFoundError(MetadataError):
    """The requested media item does not exist."""
