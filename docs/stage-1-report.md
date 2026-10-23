# Stage 1 report

## Stage

Stage 1 — project skeleton.

## Completed

- Repository rules and safety boundaries.
- FastAPI application with versioned health API and OpenAPI.
- Async SQLAlchemy/SQLite setup with foreign keys, WAL, and busy timeout.
- Initial Alembic migration.
- Vue 3 strict TypeScript shell with Router, Pinia bootstrap, theme variables,
  responsive layout, visible keyboard focus, and live API readiness state.
- Multi-stage Docker images, isolated Compose network, persistent DB bind mount,
  health checks, restart policies, and conservative memory limits.
- Backend and frontend tests plus required project documentation.

## Checks and results

- `docker compose config --quiet`: passed.
- Production and test image builds: passed for `api`, `api-test`, `web`, and
  `web-test` on ARM64.
- Pytest: 2 passed (health API and SQLite PRAGMA behavior).
- Ruff: all checks passed.
- Vitest: 1 test file, 2 tests passed (ready and unavailable API states).
- `vue-tsc -b`: passed with strict TypeScript.
- Vite production build: passed; JS bundle 91.73 kB (36.09 kB gzip), CSS 6.31
  kB (2.14 kB gzip).
- `npm audit --audit-level=moderate`: 0 vulnerabilities.
- Compose integration: `api` and `web` both healthy; UI, docs, and API returned
  HTTP 200 through port 8180.
- Health response: database `ok`; local response time measured at about 14 ms.
- Persistence/migration check after container recreation: revision
  `0001_initial`, tables `alembic_version` and `application_state`, WAL active.
- Idle snapshot: API about 51 MiB RAM / 0.38% CPU; web about 3 MiB RAM / 0.01%
  CPU. These are local ARM64 measurements, not Debian performance claims.
- Logs inspected after recreation: no application errors; nginx runs one worker.

The target Debian host and Photodom were deliberately not accessed or changed.

## Known issues

- Authentication, catalogue, metadata, indexers, torrents, streaming, library,
  cache lifecycle, and PWA are later stages.
- The actual Debian x86_64 environment still needs a read-only preflight.
- SQLite backup/restore automation is specified but not implemented in Stage 1.

## Next actions

After Debian preflight and Stage 1 acceptance, begin Stage 2 with the original
design system, catalogue domain models, TMDB adapter, caching, and real search.

## Created files

- Root/infrastructure: `.dockerignore`, `.env.example`, `.gitignore`,
  `AGENTS.md`, `Makefile`, `README.md`, `docker-compose.yml`, and
  `data/database/.gitkeep`.
- Backend: `backend/Dockerfile`, `backend/README.md`, `backend/alembic.ini`,
  `backend/docker-entrypoint.sh`, `backend/pyproject.toml`, all modules under
  `backend/app/`, the Alembic environment and initial migration under
  `backend/migrations/`, and two test files under `backend/tests/`.
- Frontend: `frontend/Dockerfile`, `frontend/index.html`, `frontend/nginx.conf`,
  `frontend/package.json`, `frontend/package-lock.json`, TypeScript/Vite config,
  and the Vue application, styles, API client, router, layout, page, and tests
  under `frontend/src/`.
- Documentation: `docs/api.md`, `docs/architecture.md`, `docs/deployment.md`,
  `docs/infrastructure-audit.md`, `docs/stage-1-report.md`, `docs/storage.md`,
  `docs/streaming.md`, and `docs/troubleshooting.md`.

