# Storage

Stage 1 persists only SQLite at `./data/database/kadr.db`. The API container
mounts that directory at `/data`; the location and database URL are
configurable. SQLite enables foreign keys, WAL, and a five-second busy timeout.

Use WAL only on a compatible local filesystem (the planned Debian ext4 storage
is appropriate after verification). Backups must use SQLite's online backup
mechanism or a coordinated checkpoint/copy, not an arbitrary live-file copy.

No media directories are mounted and no delete operation exists in Stage 1.
Future cache/library code must receive configured KADR-only roots, resolve
canonical paths, reject traversal/symlink escapes, protect `SAVED` and active
files, and never have write access to Photodom.

