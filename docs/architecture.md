# Architecture

## Stage 1 boundaries

The first increment establishes two independently testable applications:

```text
browser -> :8180 nginx/Vue -> /api/* -> FastAPI -> async SQLAlchemy -> SQLite
```

Only nginx publishes a host port. FastAPI is reachable solely on the isolated
`kadr-internal` bridge network. SQLite lives in `data/database/kadr.db`, a bind
mount outside the container. Alembic upgrades the schema before Uvicorn starts.

The backend is split into API, schema, service, repository, model, and core
layers. Empty domain package boundaries reserve the integration seams described
in the specification without pretending those features exist. The frontend
uses Vue Router, Pinia-ready bootstrapping, a dedicated API client, layouts,
pages, components, composables, stores, styles, and types.

## Technical risks

| Risk | Impact | Current mitigation / required validation |
| --- | --- | --- |
| Competing with Photodom for CPU, RAM, ports, and disk I/O | Existing service degradation | Separate Compose/network/data; conservative memory limits; only port 8180; audit the actual Debian host before deployment. |
| SQLite writer contention and network filesystems | Locks, corrupt or ineffective WAL behavior | Async sessions, short transactions, busy timeout, WAL; keep DB on local ext4 and test backup/restore. Never place it on NFS/SMB. |
| Bind-mount ownership differs across hosts | API cannot migrate/write DB | Configurable UID/GID; validate and prepare only the KADR data directory during deployment. |
| SQLite migration failure during startup | API remains unavailable | Alembic runs before Uvicorn and container health exposes failure; add automatic pre-upgrade backup in a later deployment-hardening step. |
| ARM development vs x86_64 Debian production | Image or dependency mismatch | Official multi-architecture base images; final acceptance must build and run on Debian x86_64. |
| External metadata/indexer outages | Slow or failed catalogue requests | Future adapters need strict timeouts, caching, retries with backoff, and controlled errors. |
| Torrent and streaming I/O pressure | Playback or Photodom degradation | Not implemented; future managers need bounded concurrency, free-space gates, and playback-aware scheduling. |
| Browser/TV codec fragmentation | Unsupported playback | Capability checks and honest errors; Direct Play first, no automatic transcoding. |
| Path traversal or unsafe cache deletion | Loss of unrelated or saved data | Future storage services must canonicalize and enforce KADR roots; no deletion code exists in Stage 1. |
| Public exposure of internal services/secrets | Account or host compromise | Only web entry point published; secrets server-side; auth and rate limiting are required before remote exposure. |

## Stage dependencies

Stage 2 builds catalogue/UI/TMDB on this API shell. Stage 3 introduces the
Prowlarr adapter. Stage 4 introduces the qBittorrent adapter. Stage 5 may build
streaming only after torrent state is real and tested. Stage 6 owns library and
cache lifecycle. TV, remote-access, and stabilization work follow those layers.

