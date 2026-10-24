# Stage 3 report

## Completed implementation

- Added a digest-pinned Prowlarr 2.6.5 service with persistent KADR-only data,
  health check, restart policy, memory limit, private Compose networking, and a
  loopback-only setup port.
- Added server-only Prowlarr configuration and a typed async adapter using the
  `X-Api-Key` header and official `/api/v1/search` and `/api/v1/indexer`
  endpoints.
- Added media-aware source search, torrent-only filtering, safe response
  normalization, stable opaque release IDs, five sort modes, and consistent
  provider errors.
- Added a conservative Release Parser for resolution, source, codec, HDR,
  audio, language, and release type.
- Added compatibility for indexers such as RuTor that classify results as
  `Other (8000)`, plus localized-title search with original-title fallback.
- Added a manual source-search panel to movie and series pages. No background
  polling or automatic searches are performed.
- Deliberately excluded raw provider payloads, API keys, magnet/download URLs,
  torrent addition, progress, qBittorrent, playback, and streaming.

## Verification so far

- All four KADR images build successfully.
- Pytest: 14 passed.
- Ruff: all checks passed.
- Vitest: 4 files, 6 tests passed.
- Strict TypeScript check passed.
- `api`, `web`, and `prowlarr` report healthy.
- Real Prowlarr API authentication succeeded; detected version 2.6.5.5623 and
  SQLite storage.
- Configured RuTor passed Prowlarr's connection test and is visible through
  KADR as an enabled public torrent indexer.
- End-to-end KADR → TMDB → Prowlarr → RuTor search returned HTTP 200 and 54
  normalized releases for a real movie query.

## Acceptance status

Stage 3's acceptance criterion is met: a media page can request and display
real normalized releases from the configured source. No torrent was selected,
added, or downloaded during verification.

## Changed files

- Runtime/configuration: `.env.example`, `.gitignore`, `docker-compose.yml`,
  `data/prowlarr/.gitkeep`.
- Backend: `backend/app/core/config.py`, `backend/app/main.py`,
  `backend/app/api/dependencies.py`, `backend/app/api/v1/router.py`,
  `backend/app/api/v1/sources.py`, `backend/app/schemas/sources.py`, and
  `backend/app/services/sources/`.
- Backend tests: `backend/tests/test_sources.py`.
- Frontend: `frontend/src/pages/MediaDetailsPage.vue`,
  `frontend/src/components/SourcesPanel.vue`,
  `frontend/src/services/api.ts`, `frontend/src/types/media.ts`, and
  `frontend/src/styles/main.css`.
- Frontend tests: `frontend/src/components/SourcesPanel.test.ts` and
  `frontend/src/services/api.test.ts`.
- Documentation: `README.md`, `docs/api.md`, `docs/architecture.md`,
  `docs/deployment.md`, `docs/prowlarr.md`, `docs/storage.md`,
  `docs/streaming.md`, `docs/troubleshooting.md`, and this report.

## Next action

Review and commit the RuTor compatibility update. Begin Stage 4 only after its
qBittorrent and storage-safety boundaries have been reviewed separately.
