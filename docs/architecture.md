# Architecture

## Stage 6 boundaries

The current increment keeps the frontend, API, and indexer integration
independently testable:

```text
browser -> :8180 nginx/Vue -> /api/* -> FastAPI -> TMDB adapter
                                      -> async SQLAlchemy -> SQLite cache
                                      -> Prowlarr adapter -> configured indexers
                                      -> qBittorrent adapter -> KADR download cache
                                      -> Streaming Manager -> read-only video file
                                      -> Compatibility Manager -> FFmpeg -> MP4 cache
                                      -> Library Manager -> isolated saved media
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
magnet links, credentials, and raw provider payloads. The server-side Torrent
Manager resolves the opaque source ID, passes the URI to qBittorrent, and
exposes only normalized task/file state to the browser.

qBittorrent persists configuration in `data/qbittorrent` and can write only to
`data/downloads`. Its Web UI is bound to host loopback. The API sees the same
download filesystem read-only for free-space checks and Direct Play. A magnet may run
only long enough to receive metadata, using qBittorrent's
`MetadataReceived` stop condition. Once files are visible, KADR disables all of
them until the user selects one supported video. Active-download concurrency
and minimum free space are configurable. The UI refreshes metadata and active
download progress every five seconds only while work is pending. For a series,
the user may explicitly queue the next few episodes or every recognized episode
from the selected season; the current playback selection remains unchanged.

The Streaming Manager resolves the selected file only beneath the configured
KADR storage root, maps file offsets to torrent pieces, and checks
qBittorrent's authoritative piece state before every filesystem read. The
initial buffer starts at one response chunk, grows to four seconds of current
download speed, and is capped by the configured target and requested range.
The selected file keeps normal priority so qBittorrent's sequential picker is
not displaced by maximal file priority. Missing data is awaited only up to the
configured timeout. An in-memory registry limits concurrent torrent tasks and
also caps parallel Range requests per task. This lets one native browser player
replace or overlap HTTP ranges without consuming several viewer slots. Leases
are released when each response finishes or its client disconnects. The API
never sends a sparse or not-yet-complete piece.

The Vue player uses native browser controls and requests the same-origin range
endpoint through nginx. It is created only after an explicit user action,
offers locally saved resume position, and tears down its media source when
closed. Playback is Direct Play: the browser must support the selected
container, video codec, and audio codec.

The Compatibility Manager is an explicit fallback. It canonicalizes a
completed selected source beneath the read-only KADR download root, probes its
real streams, and chooses remux, audio-only conversion, or bounded H.264/AAC
conversion. A process-local scheduler permits one FFmpeg job by default. Work
is written to a temporary file under the separate writable playback cache and
atomically renamed only on success. Generated MP4 ranges share the Streaming
Manager's request registry. Opening Direct Play never starts FFmpeg.

The Library Manager accepts only a fully downloaded selected file whose
canonical source remains beneath the configured KADR download root. It writes
to a separate library root with hard-link-first/copy fallback and atomic
publication. Saved-file Range streams use registry keys, so active items
cannot be deleted. Favorites and watch history are persistent SQLite records.

The series source view uses the trusted metadata season list to issue bounded
season-specific searches with `S01`-style markers. Every regular season gets a
collapsed group, including an explicit empty state when no release was found.
The requested season travels with the opaque release ID so resolution repeats
the same search. A direct whole-season action selects the first episode and
queues the remaining video files after metadata arrives. Generic fallback
searches still group normalized results by release-title season markers and
keep ambiguous results visible. Prowlarr persists its own configuration in `data/prowlarr`
and exposes its administrative UI only on host loopback. It is not a dependency of API health:
catalogue browsing continues when Prowlarr or an indexer is unavailable.

FlareSolverr is an internal-only browser-challenge adapter on the KADR network.
Prowlarr reaches it at `http://flaresolverr:8191`; no host port is published.
Prowlarr applies it only to indexers sharing an explicit proxy tag. The
container is unprivileged, resource-limited, and uses RAM-backed temporary
browser profiles. A hard Cloudflare IP block can still reject the request.

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
| Torrent I/O pressure | Host or Photodom degradation | Stopped-by-default additions, bounded active torrents, configurable free-space gate, low-rate polling only for the open task, and qBittorrent memory limit; validate host headroom before deployment. |
| Browser/TV codec fragmentation | Unsupported playback | Direct Play first; explicit ffprobe/FFmpeg fallback produces H.264/AAC MP4, with honest errors for remaining device limits. |
| FFmpeg CPU, memory, and disk-I/O pressure | Existing services become slow or playback cache fills storage | Explicit-only jobs, one-job/two-thread defaults, 1080p cap, container CPU/RAM limits, free-space reserve, separate cache; validate production host headroom. |
| Corrupt or malicious media input | FFmpeg failure or excessive processing | Unprivileged container, no-new-privileges, read-only source mount, bounded concurrency, exact argv execution without a shell, controlled failure state. |
| qBittorrent Web API cannot prioritize an arbitrary piece range | A long seek into an incomplete file can time out | Enable sequential and first/last-piece modes, reassert maximum file priority, wait only for verified pieces, and evaluate a libtorrent-capable adapter before claiming arbitrary seek-priority optimization. |
| A stream fails after response headers are sent | Browser sees a network/media error rather than a JSON body | Validate the initial buffer before returning headers; surface later starvation as a player error and keep timeout bounded. |
| Process restart loses active-stream counters | Temporary concurrency accounting reset | Registry is deliberately process-local for the single-worker MVP; use shared coordination before adding API replicas. |
| Malicious torrent paths or unsafe cache deletion | Filesystem escape or data loss | Canonical paths must stay beneath KADR roots; active and saved tasks are protected; qBittorrent deletes only known expired tasks. |
| Public exposure of internal services/secrets | Account or host compromise | Only web entry point published; secrets server-side; auth and rate limiting are required before remote exposure. |

## Stage dependencies

Stages 1-6 provide the shell, catalogue, source discovery, qBittorrent control,
Direct Play, compatible playback, library, history, favorites, and guarded
cache lifecycle. TV, remote-access, and stabilization work follow those layers.

