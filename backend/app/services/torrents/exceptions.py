class TorrentNotConfiguredError(RuntimeError):
    """Raised when qBittorrent credentials are absent or rejected."""


class TorrentUnavailableError(RuntimeError):
    """Raised when qBittorrent cannot complete an operation."""


class TorrentNotFoundError(RuntimeError):
    """Raised when a KADR torrent task or source no longer exists."""


class TorrentLimitError(RuntimeError):
    """Raised when the configured active torrent limit is reached."""


class TorrentFileError(RuntimeError):
    """Raised when a requested torrent file cannot be selected."""


class TorrentStorageError(RuntimeError):
    """Raised when the configured KADR storage cannot safely accept downloads."""
