class PlaybackPreparationError(RuntimeError):
    """Raised when a compatible playback artifact cannot be prepared."""


class PlaybackPreparationLimitError(RuntimeError):
    """Raised when the configured FFmpeg concurrency limit is reached."""


class PlaybackArtifactNotReadyError(RuntimeError):
    """Raised when the compatible playback artifact is not ready."""


class PlaybackTrackProbeError(RuntimeError):
    """Raised when local media tracks cannot be inspected safely."""


class PlaybackTrackPreferenceError(RuntimeError):
    """Raised when a requested media track does not belong to the source."""


class PlaybackSubtitleError(RuntimeError):
    """Raised when an explicitly selected subtitle cannot be prepared."""
