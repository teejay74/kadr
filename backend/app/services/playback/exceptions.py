class PlaybackPreparationError(RuntimeError):
    """Raised when a compatible playback artifact cannot be prepared."""


class PlaybackPreparationLimitError(RuntimeError):
    """Raised when the configured FFmpeg concurrency limit is reached."""


class PlaybackArtifactNotReadyError(RuntimeError):
    """Raised when the compatible playback artifact is not ready."""
