# Architecture

## Stage 3 boundaries

The current increment keeps the frontend, API, and indexer integration
independently testable:

```text
browser -> :8180 nginx/Vue -> /api/* -> FastAPI -> TMDB adapter
                                      -> async SQLAlchemy -> SQLite cache
                                      -> Prowlarr adapter -> configured indexers
```

Only nginx publishes a LAN-facing host port. Prowlarr's setup port is bound to
host loopback; FastAPI is reachable solely on the isolated `kadr-internal`
bridge network. SQLite lives in `data/database/kadr.db`, a bind mount outside
the container. Alembic upgrades the schema before Uvicorn starts.

The backend is split into API, schema, service, repository, model, and core
layers. Thin catalogue controllers call `CatalogService`; it depends on a TMDB
adapter and a metadata-cache repository. Requests have a strict timeout, use a
short-lived persistent cache, and may serve expired cached metadata only while
TMDB is unavailable. The token never reaches the browser.

The responsive frontend uses Vue Router, Composition API, strict TypeScript,
reusable media components, and a dedicated API client. It provides home rails,
film and series catalogues, filters, pagination, search, detail pages, cast and
season summaries. Empty integration packages continue to reserve later seams
without presenting future features as implemented.

Source search is explicitly user-triggered. The source service first resolves
the trusted title and year from the metadata service, then calls Prowlarr over
the private Compose network. A dedicated Release Parser derives only attributes
present in the release title. The public API omits Prowlarr download URLs,
magnet links, credentials, and raw provider payloads; those are reserved for a
future server-side Torrent Manager.

Prowlarr persists its own configuration in `data/prowlarr` and exposes its
administrative UI only on host loopback. It is not a dependency of API health:
catalogue browsing continues when Prowlarr or an indexer is unavailable.

## Technical risks

| Risk | Impact | Current mitigation / required validation |
| --- | --- | --- |
| Competing with Photodom for CPU, RAM, ports, and disk I/O | Existing service degradation | Separate Compose/network/data; conservative memory limits; LAN port 8180 and loopback-only 9696; audit the actual Debian host before deployment. |
| SQLite writer contention and network filesystems | Locks, corrupt or ineffective WAL behavior | Async sessions, short transactions, busy timeout, WAL; keep DB on local ext4 and test backup/restore. Never place it on NFS/SMB. |
| Bind-mount ownership differs across hosts | API cannot migrate/write DB | Configurable UID/GID; validate and prepare only the KADR data directory during deployment. |
| SQLite migration failure during startup | API remains unavailable | Alembic runs before Uvicorn and container health exposes failure; add automatic pre-upgrade backup in a later deployment-hardening step. |
| ARM development vs x86_64 Debian production | Image or dependency mismatch | Official multi-architecture base images; final acceptance must build and run on Debian x86_64. |
| External metadata outage or quota limit | Slow or failed catalogue requests | Eight-second configurable timeout, persistent TTL cache, stale-on-outage fallback, controlled 502 errors, and bounded page sizes. |
| Missing or leaked TMDB credential | Catalogue unavailable or credential compromise | Server-only secret configuration, no token logging or frontend exposure, and a controlled 503 setup state. |
| Upstream schema drift or incomplete artwork | Broken cards/details | Typed normalized API schemas, defensive optional-field mapping, placeholders, and adapter tests. |
| Indexer credentials or download URLs leak to browsers/logs | Tracker account compromise | Server-only `X-Api-Key`; normalized allowlisted response fields; no raw, magnet, or download URLs in Stage 3. |
| Slow, rate-limited, or unavailable indexers | Delayed source search | User-triggered requests, bounded result count, configurable timeout, no background polling, controlled 502 errors. |
| Incorrect quality inference from release names | Misleading source choice | Conservative parser with nullable attributes and a tested pattern matrix; no media probing claims. |
| Torrent and streaming I/O pressure | Playback or Photodom degradation | Not implemented; future managers need bounded concurrency, free-space gates, and playback-aware scheduling. |
| Browser/TV codec fragmentation | Unsupported playback | Capability checks and honest errors; Direct Play first, no automatic transcoding. |
| Path traversal or unsafe cache deletion | Loss of unrelated or saved data | Future storage services must canonicalize and enforce KADR roots; no deletion code exists through Stage 3. |
| Public exposure of internal services/secrets | Account or host compromise | Only web entry point published; secrets server-side; auth and rate limiting are required before remote exposure. |

## Stage dependencies

Stages 1-3 provide the shell, metadata catalogue, and Prowlarr source discovery.
Stage 4 introduces the qBittorrent adapter. Stage 5 may build
streaming only after torrent state is real and tested. Stage 6 owns library and
cache lifecycle. TV, remote-access, and stabilization work follow those layers.

