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
- Added a manual source-search panel to movie and series pages. No background
  polling or automatic searches are performed.
- Deliberately excluded raw provider payloads, API keys, magnet/download URLs,
  torrent addition, progress, qBittorrent, playback, and streaming.

## Verification so far

- All four KADR images build successfully.
- Pytest: 13 passed.
- Ruff: all checks passed.
- Vitest: 4 files, 6 tests passed.
- Strict TypeScript check passed.
- `api`, `web`, and `prowlarr` report healthy.
- Real Prowlarr API authentication succeeded; detected version 2.6.5.5623 and
  SQLite storage.
- End-to-end KADR → TMDB → Prowlarr request returned HTTP 200 and a truthful
  empty result.

## Acceptance status and known issue

No indexer is configured yet. Therefore Stage 3's final acceptance criterion —
displaying real releases from a configured source — has not yet been claimed.
The owner must configure and test an authorized torrent indexer in the local
Prowlarr UI; KADR must then be retested with a real non-empty response.

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

Configure one authorized torrent indexer at `http://127.0.0.1:9696`. After a
successful Prowlarr test, repeat the KADR source search, review the normalized
fields, update this report with the live result, and only then finalize Stage 3.
