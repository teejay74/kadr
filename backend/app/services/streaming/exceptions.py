class StreamNotReadyError(RuntimeError):
    """Raised when a torrent cannot be prepared for Direct Play."""


class StreamBufferTimeoutError(RuntimeError):
    """Raised when requested pieces do not arrive before the configured timeout."""


class StreamLimitError(RuntimeError):
    """Raised when the concurrent Direct Play limit is reached."""


class StreamRangeError(ValueError):
    """Raised when an HTTP byte range cannot be satisfied."""

    def __init__(self, total_size: int) -> None:
        super().__init__("The requested byte range cannot be satisfied")
        self.total_size = total_size
