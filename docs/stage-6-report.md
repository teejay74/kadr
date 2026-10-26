# Stage 6 report — Media library

Date: 2026-10-25

## Completed

- Added migrated SQLite models for saved library items, favorites, and watch history.
- Added explicit save of a fully downloaded selected video with hard-link-first,
  safe-copy fallback, temporary output, and atomic rename.
- Added an isolated library mount and HTTP Range playback independent of the
  torrent source.
- Added protected deletion with canonical-root and active-stream checks.
- Added favorites and server-side playback resume/completion updates.
- Added a Library page with saved byte totals, playback, favorites, and
  confirmation before deletion.
- Added guarded manual and low-frequency TTL cache cleanup. Active downloads,
  active streams, and saved tasks are skipped.
- Added storage status for library/cache counts, bytes, and free space.
- Added an explicit whole-season download action for recognized `S01E01` and
  `1x01` episode names while preserving the current playback selection.
- Grouped series source results by single seasons and season ranges inferred
  from release titles, with ambiguous releases retained in a separate group.

## Safety boundaries

- The API can write only its database, playback cache, and KADR library mount;
  torrent downloads remain read-only to it.
- No Photodom path is mounted, inspected, changed, or deleted.
- Library and download paths are canonicalized against configured KADR roots.
- Cache deletion targets only a known expired database task through the
  isolated qBittorrent instance after saved/active checks.

## Verification

- Backend Pytest: `52 passed`.
- Frontend Vitest: `20 passed` across 6 files.
- Ruff: passed; TypeScript check and production Vite build: passed.
- Alembic migrated the live local database from `0003` to `0004_library`.
- Compose configuration is valid; API, web, Prowlarr, and qBittorrent are healthy.
- Live `/system/health`, `/library`, `/favorites`, and `/system/storage`
  requests returned `200` through nginx.
- Live storage status reported 8 cache tasks and 4,593,544,425 downloaded
  bytes. Cleanup was deliberately not invoked during acceptance, so existing
  media was not removed.

## Known limitations

- The current local profile is single-user; role-based accounts are required
  before untrusted or public access.
- Saving a season currently stores the selected episode as the media entry;
  episode-aware grouping needs richer season/episode identity.
- Compatible FFmpeg artifacts retain their separate playback-cache lifecycle.

## Next action

Stage 7 adds directional TV focus, remote-control interaction, player
adaptation, and a measured Android TV / Google TV compatibility matrix.

## Follow-up verification — 2026-10-26

- Backend Pytest: `62 passed`.
- Frontend Vitest: `27 passed` across 6 files.
- Changed Python files pass Ruff; the whole-tree check still reports three
  pre-existing E501 lines in migration `0004_library.py`.
- TypeScript check and production Vite build passed.
- Compose configuration validation passed. The application stack was not
  running during this local verification, so no live health or log check was
  performed.

## Seasonal source follow-up — 2026-10-26

### Completed work

- Replaced the single generic series search with bounded, season-specific
  searches using the TMDB season list and `S01`-style query markers.
- Seeded the results view with every known regular season, including seasons
  for which an indexer returned no releases.
- Made all series source groups collapsed by default.
- Added «Скачать сезон» directly to each seasonal release. It selects the
  first episode for playback and queues the remaining video files once torrent
  metadata arrives.
- Preserved the requested season through opaque source resolution so no raw
  provider URL or magnet is exposed to the browser.

### Changed files

- Backend source schemas, endpoint, search service, and torrent add flow.
- Frontend API client, media details integration, source panel, styles, and
  focused component/API tests.
- `README.md`, `docs/api.md`, and this stage report.

### Checks

- Backend Pytest: 64 passed.
- Frontend Vitest: 31 passed across 6 files.
- Ruff passed with its cache disabled because the test container filesystem is
  read-only; TypeScript production build passed.
- Compose configuration validation passed.
- `docker compose ps` confirmed that the local application stack was not
  running, so no local service logs or live health endpoint were available to
  inspect.

### Known issues and next actions

- Indexer quality still determines whether a matching seasonal release exists;
  an empty season remains visible with an explicit no-results message.
- Inspect live service health/logs after deploying this follow-up.

## Multi-season and playback-status follow-up — 2026-10-26

### Completed work

- Added conservative source-title parsing for single seasons, explicit lists,
  and ranges including `S01-05`, `S01-S05`, episode-spanning ranges, English,
  and Russian season labels.
- Distinguished episode ranges such as `S1E1-9` from season ranges; only an
  explicit second `S` marker makes an episode-spanning title multi-season.
- Added support for compact multi-season/episode ranges such as `S1-2E1-18`,
  while retaining `S1E1-9` as a single-season release.
- Separated release coverage from the season-specific search context, grouped
  multi-season packs independently, and deduplicated the same opaque source
  across seasonal searches.
- Added a season picker for multi-season packs and validation against torrent
  file names before queuing the selected season.
- Kept the player frame visible while the initial buffer is pending and added
  explicit selected-file download percentage, torrent state, speed, buffer
  progress, polling explanation, and browser autoplay errors.

### Changed files

- Backend source schema, release parser, search normalization, and parser tests.
- Frontend source grouping/download controls, player state UI, styles, types,
  and component tests.
- `README.md`, `docs/api.md`, `docs/architecture.md`, `docs/streaming.md`, and
  this report.

### Checks

- Backend Pytest after the season/episode range fixes: 76 passed.
- Frontend Vitest: 33 passed across 6 files.
- Ruff passed; TypeScript checking and the production Vite build passed.
- Compose configuration validation passed.
- Server logs confirmed that the playback action reached the readiness API;
  the selected torrent was still waiting for its initial stream buffer and no
  stream request had started yet.

### Known issues and next actions

- Release-title parsing remains conservative; after torrent metadata arrives,
  recognized file paths are treated as the stronger season identity.
- Inspect live service health after this follow-up is deployed.

## Fast audio repair and idempotent library save — 2026-10-26

### Completed work

- Added an explicit fast FFmpeg mode that copies an already playable video
  stream and converts only its first audio track to AAC stereo.
- Kept fast and fully compatible artifacts separate and tagged copied HEVC as
  `hvc1` for MP4 playback.
- Made concurrent duplicate library inserts return the existing media item
  instead of leaking a database uniqueness error as HTTP 500.
- Stopped the user-authorized test FFmpeg process on the Debian host and
  confirmed that the KADR API remained healthy.

### Checks

- Backend Pytest: 78 passed.
- Frontend Vitest: 35 passed across 6 files; TypeScript production build
  passed.
- Ruff passed with its cache disabled because the test container filesystem is
  read-only.
- Compose configuration validation and `git diff --check` passed.

## Library streaming range fix — 2026-10-26

### Completed work

- Fixed the saved-library stream response to use the shared `ByteRange.total`
  field when constructing `Content-Range`.
- Added an API-level regression test covering a browser-style byte-range
  request and its `206`, `Content-Range`, length, and payload.
- Confirmed on the Debian host that the previous exception leaked stream
  leases until the global stream limit rejected all subsequent playback with
  HTTP 429.

### Checks

- Backend Pytest: 78 passed.
- Ruff, Compose configuration validation, and `git diff --check` passed.

### Known issues and next actions

- Deployment must recreate the API container once to clear stream leases left
  in memory by requests that failed before this fix.
