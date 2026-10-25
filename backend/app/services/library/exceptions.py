class LibraryError(Exception):
    """Base library error."""


class LibraryNotFoundError(LibraryError):
    pass


class LibraryConflictError(LibraryError):
    pass


class LibraryStorageError(LibraryError):
    pass
