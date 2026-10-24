# Storage

Stage 4 persists SQLite at `./data/database/kadr.db`. In addition to application
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

No delete operation exists in Stage 4. Future cache/library code must receive
configured KADR-only roots, resolve
canonical paths, reject traversal/symlink escapes, protect `SAVED` and active
files, and never have write access to Photodom.

KADR also persists Prowlarr configuration and its private database under
`./data/prowlarr`. This directory may contain API keys, cookies, and tracker
credentials. It is excluded from Git, must not be copied into logs or reports,
and needs the same restricted backup handling as other secrets. Prowlarr has no
media-directory mount and cannot access Photodom or future KADR media paths.

