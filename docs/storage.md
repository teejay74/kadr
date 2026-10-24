# Storage

Stage 3 persists SQLite at `./data/database/kadr.db`. In addition to application
state, the database holds normalized TMDB response-cache records with expiry
timestamps. The API container
mounts that directory at `/data`; the location and database URL are
configurable. SQLite enables foreign keys, WAL, and a five-second busy timeout.

Use WAL only on a compatible local filesystem (the planned Debian ext4 storage
is appropriate after verification). Backups must use SQLite's online backup
mechanism or a coordinated checkpoint/copy, not an arbitrary live-file copy.

No media directories are mounted and no delete operation exists in Stage 3.
Future cache/library code must receive configured KADR-only roots, resolve
canonical paths, reject traversal/symlink escapes, protect `SAVED` and active
files, and never have write access to Photodom.

Stage 3 also persists Prowlarr configuration and its private database under
`./data/prowlarr`. This directory may contain API keys, cookies, and tracker
credentials. It is excluded from Git, must not be copied into logs or reports,
and needs the same restricted backup handling as other secrets. Prowlarr has no
media-directory mount and cannot access Photodom or future KADR media paths.

