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
season summaries. UI redesign substage B1 separates the shared hero, actions,
play button, cast carousel, season selector, episode list/cards, playback
progress, and media status into focused components. A series season is loaded
on demand from the metadata service and the last selected season is remembered
in browser storage. In substage C1, the film action and episode cards use one
backend resolver and render the same player component. The legacy source panel
remains available as a manual fallback until its replacement selector is
implemented and verified. Empty integration packages continue to reserve later
seams without presenting future features as implemented.

Episode catalogue identity is stored independently as series ID, season number,
episode number, and optional provider episode ID. A separate file-variant row
identifies a physical `task_id`/`file_id`, while an association table connects
logical episodes to one or more variants. Therefore one torrent task can bind
different episodes to different files and one episode can later expose several
quality variants. The legacy `torrent_tasks.selected_file_id` and selected path
remain the active playback selection for backward compatibility; they are not
the episode identity.

`EpisodeMatcher` sits between torrent-file discovery, TMDB metadata, and the
episode repository. It parses the complete relative path (including season
folders), validates explicit identities against provider metadata, and uses
title similarity plus already available duration only as secondary evidence.
It has no LLM or machine-learning dependency and never triggers a media
download or FFmpeg probe. Only unique, conflict-free `exact` matches are
written automatically; `probable` and `ambiguous` candidates are returned to a
Vue confirmation dialog. Confirmed mappings retain confidence and automatic or
manual provenance in SQLite and are reused after process restart. The
many-to-many data model supports combined episodes and multiple physical
variants; an optional segment index reserves a future multipart seam, but this
increment neither concatenates files nor invents seek boundaries inside a
combined video.

Substage C2 adds a modal `SourceSelector` to the unified playback flow. It opens
only after `source_required`, `unavailable`, or an explicit “Другой источник”
action. It shows normalized quality, release type, size, language/audio, and
seed availability while keeping the raw release title in an opt-in technical
details block. Its recommendation is a convenience score, not a liveness
claim. After the user selects a release, the browser waits only for torrent
metadata; the backend still owns concrete file choice. Films use the largest
safe supported video selected by Torrent Manager. Series run Episode Matcher
and open the existing confirmation dialog when the requested episode is not
already confirmed. The unified resolver is retried only after that preparation.
The legacy source panel remains mounted for regression and manual recovery.

Substage D1 places series ordering in `EpisodeNavigationService`. It reads
TMDB season episode lists, crosses to the first catalog episode of the next
regular season, and asks the existing Playback Resolver to reuse a confirmed
variant with the current torrent task preferred. A separate opportunistic
path calls Torrent Manager prefetch with exactly one next file; it preserves
the active selection and never queues a whole season. `NextEpisodeOverlay`
owns only presentation, countdown, and the local autoplay preference. It does
not calculate episode identity. A shared physical file bound to consecutive
logical episodes is marked as combined and is not treated as a precise seek
target without time-boundary metadata.

The final D2 increment separates viewing from download administration.
`DownloadsPage` consumes a bounded `GET /api/v1/torrents` projection and polls
only while an incomplete task is active, at a ten-second interval. Torrent
Manager joins recent KADR database tasks to one qBittorrent list response;
missing external tasks are represented as unavailable rather than triggering
one request per card. File lists remain on-demand. Pause/resume and protected
completed-file deletion use the existing endpoints and safety checks. Media
details no longer mount technical torrent controls; the legacy
`SourcesPanel.vue` file remains available for rollback until real Debian
playback acceptance is complete.

Library items optionally reference a logical episode and record the selected
file ID. Watch history optionally references a logical episode and is scoped by
`profile_key` (currently `default` unless a caller supplies another profile).
SQLite partial unique indexes distinguish title-level rows, whose episode ID is
NULL, from episode-level rows. This avoids SQLite's nullable-unique loophole
while preserving pre-B2 library and history records.

The Playback Resolver accepts title identity plus optional logical episode and
profile identity. It reads resume history, prefers an available saved-library
copy, then reuses persisted episode/file variants. For a film it can reuse the
latest task's backward-compatible selected file. It never derives episode
identity from a filename. The resolver selects the exact file through the
Torrent Manager and asks the Streaming Manager for piece-level readiness before
returning `ready` or `buffering`; missing and stale sources return explicit
`source_required` or `unavailable` states. The browser does not choose a file
or infer readiness from overall download percentage. Player readiness polling
is bounded to twelve five-second checks so a stalled source does not leave an
unending loading state. Readiness also returns the exact selected-file progress;
prefetched files no longer distort the player percentage. MKV/WebM and transport
streams gate startup on their initial pieces, while containers with trailing
metadata requirements retain a bounded tail probe.

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

The Playback Track service is a separate read-only discovery layer. It accepts
only the currently selected, fully downloaded torrent file or one explicit
library item, canonicalizes the source under its KADR-owned root, and invokes
`ffprobe` with a bounded timeout and no shell. Results are cached in process by
canonical path, size, and modification time. Exact per-file IDs remain distinct
from semantic preference keys, allowing a later preference resolver and native
Android TV client to select by language/title/codec instead of assuming that
stream indexes are stable. Discovery classifies text, bitmap, and unsupported
subtitle delivery but never starts FFmpeg or changes Direct Play.

The Library Manager accepts only a fully downloaded selected file whose
canonical source remains beneath the configured KADR download root. It writes
to a separate library root with hard-link-first/copy fallback and atomic
publication. Saved-file Range streams use registry keys, so active items
cannot be deleted. An episode save is idempotent for its logical episode, while
legacy film/title saves remain idempotent at media level. Cache deletion protects
the exact saved task/file and whole-task cleanup protects every task referenced
by a saved item. Favorites and profile/episode-aware watch history are
persistent SQLite records.

The series source view uses the trusted metadata season list to issue bounded
season-specific searches with `S01`-style markers. Every regular season gets a
collapsed group, including an explicit empty state when no release was found.
The requested season travels with the opaque release ID so resolution repeats
the same search. Separately parsed release coverage recognizes single seasons,
lists, and ranges such as `S01-05`; duplicate packs returned by several searches
are collapsed into one result. A direct whole-season action lets the viewer
choose a season from a multi-season pack, validates it against torrent file
names, selects the first episode, and queues the remaining video files after
metadata arrives. Generic fallback
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
| Slow or malformed track metadata | API worker starvation or unsafe labels | Bounded asynchronous ffprobe subprocess, sanitized/length-limited tags, canonical KADR-root paths, and a small file-identity cache. |
| qBittorrent Web API cannot prioritize an arbitrary piece range | A long seek into an incomplete file can time out | Enable sequential and first/last-piece modes, reassert maximum file priority, wait only for verified pieces, and evaluate a libtorrent-capable adapter before claiming arbitrary seek-priority optimization. |
| A stream fails after response headers are sent | Browser sees a network/media error rather than a JSON body | Validate the initial buffer before returning headers; surface later starvation as a player error and keep timeout bounded. |
| Process restart loses active-stream counters | Temporary concurrency accounting reset | Registry is deliberately process-local for the single-worker MVP; use shared coordination before adding API replicas. |
| Malicious torrent paths or unsafe cache deletion | Filesystem escape or data loss | Canonical paths must stay beneath KADR roots; active and saved tasks are protected; qBittorrent deletes only known expired tasks. |
| Ambiguous or misleading episode filenames | Wrong episode history or playback binding | Full-path parsing, TMDB existence checks, conflict detection, exact-only automatic persistence, and explicit confirmation for probable/ambiguous candidates. |
| Public exposure of internal services/secrets | Account or host compromise | Only web entry point published; secrets server-side; auth and rate limiting are required before remote exposure. |

## Stage dependencies

Stages 1-6 provide the shell, catalogue, source discovery, qBittorrent control,
Direct Play, compatible playback, library, history, favorites, and guarded
cache lifecycle. TV, remote-access, and stabilization work follow those layers.

