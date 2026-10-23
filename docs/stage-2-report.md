# Stage 2 report

## Completed work

- Added a server-side TMDB adapter with bearer authentication, localized
  movie/series discovery, search, genres, details, credits, videos, and seasons.
- Added a persistent SQLite metadata cache with TTL and stale-on-provider-outage
  behavior, plus Alembic migration `0002_metadata_cache`.
- Added normalized versioned catalogue endpoints and consistent provider error
  responses.
- Replaced the skeleton page with a responsive catalogue UI: home rails,
  filters, pagination, search, details, cast, series seasons, loading/empty/error
  states, and mandatory TMDB attribution.
- Kept all torrent, qBittorrent, streaming, playback, deletion, and transcoding
  behavior outside this stage.

## Checks and test results

- `docker compose config --quiet`: passed.
- `docker compose build api api-test web web-test`: all four images built.
- Pytest: 6 passed (`test_catalog.py` and `test_health.py`).
- Ruff: all checks passed.
- Vitest: 3 files, 4 tests passed.
- `vue-tsc -b`: passed.
- Production runtime: `api` and `web` both reported healthy; system health
  returned `200` with database `ok`; `/openapi.json` returned `200`.
- Alembic: `0002_metadata_cache (head)` applied to the isolated KADR database.
- With no repository-supplied TMDB token, `/api/v1/movies` returned the expected
  controlled `503 metadata_not_configured` response. Live-provider acceptance
  requires the operator's token and was not simulated as completed.
- Startup logs contained no application errors or leaked credentials.

## Changed files

Configuration and documentation:

- `.env.example`, `docker-compose.yml`, `README.md`
- `docs/api.md`, `docs/architecture.md`, `docs/deployment.md`
- `docs/storage.md`, `docs/streaming.md`, `docs/troubleshooting.md`
- `docs/stage-2-report.md`

Backend:

- `backend/pyproject.toml`
- `backend/app/main.py`, `backend/app/core/config.py`
- `backend/app/api/dependencies.py`, `backend/app/api/v1/catalog.py`
- `backend/app/api/v1/router.py`
- `backend/app/models/__init__.py`, `backend/app/models/metadata_cache.py`
- `backend/app/repositories/metadata_cache.py`
- `backend/app/schemas/media.py`
- `backend/app/services/metadata/catalog.py`
- `backend/app/services/metadata/exceptions.py`
- `backend/app/services/metadata/tmdb.py`
- `backend/migrations/versions/0002_metadata_cache.py`
- `backend/tests/test_catalog.py`

Frontend:

- `frontend/src/layouts/AppShell.vue`, `frontend/src/router/index.ts`
- `frontend/src/pages/HomePage.vue`, `CatalogPage.vue`, `SearchPage.vue`
- `frontend/src/pages/MediaDetailsPage.vue`, `CreditsPage.vue`
- `frontend/src/components/MediaCard.vue`, `MediaRail.vue`, `StatePanel.vue`
- `frontend/src/components/TmdbCredit.vue`
- `frontend/src/services/api.ts`, `frontend/src/types/media.ts`
- `frontend/src/styles/main.css`
- `frontend/src/services/api.test.ts`
- `frontend/src/components/MediaCard.test.ts`, `StatePanel.test.ts`
- Removed the obsolete Stage 1 `frontend/src/pages/HomePage.test.ts`.

## Known issues and deployment prerequisites

- A user-provided TMDB API Read Access Token is required for live catalogue
  data. It is intentionally absent from the repository.
- The application has not been deployed to or audited on the Debian host.
- TMDB availability, quotas, and metadata completeness remain external
  dependencies; cached data softens temporary outages.

## Next actions

Stage 3 may add a Prowlarr search adapter only after Stage 2 is accepted. It
must not add playback or pretend that search results are playable.
