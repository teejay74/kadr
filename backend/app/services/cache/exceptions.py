class CacheFileNotFoundError(RuntimeError):
    """Raised when a requested cached file is unavailable."""


class CacheDeletionConflictError(RuntimeError):
    """Raised when safety rules prohibit deleting a cached file."""


class CacheStorageError(RuntimeError):
    """Raised when a cache path cannot be validated or changed safely."""
