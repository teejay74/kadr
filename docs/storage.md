# Storage

SQLite is persisted at `./data/database/kadr.db`. In addition to application
state, the database holds normalized TMDB response-cache records with expiry
timestamps. The API container
mounts that directory at `/data`; the location and database URL are
configurable. SQLite enables foreign keys, WAL, and a five-second busy timeout.

Use WAL only on a compatible local filesystem (the planned Debian ext4 storage
is appropriate after verification). Backups must use SQLite's online backup
mechanism or a coordinated checkpoint/copy, not an arbitrary live-file copy.

qBittorrent owns writes under `./data/downloads`, mounted as `/downloads`; the
API receives that mount read-only to check free capacity. Its configuration is
stored separately at `./data/qbittorrent`. `KADR_TORRENT_SAVE_PATH`,
`KADR_TORRENT_STORAGE_ROOT`, and `KADR_MIN_FREE_SPACE_GB` are configurable.
The save path must remain inside the qBittorrent KADR-only mount.

The API writes generated compatible MP4 files only beneath
`./data/playback`, mounted at `/playback`. Source downloads remain mounted
read-only in the API. Preparation uses a task-specific `.part.mp4` and an
atomic rename, enforces a configurable free-space reserve, and reuses a
completed artifact. Failed temporary output is removed.

Saved media lives only beneath `./data/library`, mounted at `/library`. Saving
verifies a complete selected file under the read-only download root, then
creates a hard link where supported or safely copies to a temporary file
followed by atomic rename. API responses do not expose filesystem paths.

Deletion canonicalizes the stored path against `KADR_LIBRARY_ROOT`, refuses an
active stream, unlinks only that saved file, and leaves the torrent source
untouched. Cache cleanup operates through qBittorrent only for stopped KADR
tasks older than `KADR_CACHE_TTL_HOURS`; it skips active streams and tasks
referenced by saved library items. A low-rate background pass runs every
`KADR_CACHE_CLEANUP_INTERVAL_MINUTES`. Neither service has a Photodom mount.

KADR also persists Prowlarr configuration and its private database under
`./data/prowlarr`. This directory may contain API keys, cookies, and tracker
credentials. It is excluded from Git, must not be copied into logs or reports,
and needs the same restricted backup handling as other secrets. Prowlarr has no
media-directory mount and cannot access Photodom or future KADR media paths.

