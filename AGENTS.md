# KADR development rules

These rules apply to the whole repository and are derived from
`docs/TECHNICAL_SPECIFICATION.md`.

## Delivery process

- Work in the numbered stages from the specification. Keep every stage small,
  runnable, tested, and documented before starting the next one.
- Stage 1 is the application skeleton only. Do not implement torrent search,
  qBittorrent, streaming, playback, media-library deletion, or transcoding in
  this stage.
- Do not present mocks, static catalogue data, fake progress, or untested API
  methods as completed functionality. Test doubles are allowed only in tests.
- After each stage, run the relevant tests, inspect service health/logs, update
  documentation, and write a stage report with: completed work, changed files,
  checks, test results, known issues, and next actions.

## Safety and infrastructure

- KADR must remain isolated from Photodom: separate project directory, Compose
  project, database, environment, data directories, and Docker network.
- Never read from or write to Photodom paths unless the user explicitly grants
  access. Never alter Photodom configuration or restart its services.
- Never format disks, change mounts, migrate photos, change firewall/network
  settings, delete Docker volumes, run `docker system prune`, overwrite an
  existing database, or modify an existing service without explicit approval.
- Before deployment, audit the actual Debian host, Docker services, ports,
  storage, permissions, backups, and resource headroom using read-only checks.
- Publish only the KADR web entry point. Keep SQLite and future internal
  services such as Prowlarr and qBittorrent off public interfaces.
- Containers must be unprivileged where practical, have health checks and
  restart policies, use pinned image versions, and shut down cleanly.
- All paths and limits must come from configuration. Business logic must not
  contain `/srv/storage` or other deployment-specific absolute paths.
- Destructive file operations must resolve canonical paths, remain inside an
  allowed KADR directory, and protect saved or active media.

## Architecture and code quality

- Keep API controllers thin. Put business logic in services and persistence in
  repositories. Depend on adapters/interfaces for replaceable integrations.
- Use async I/O for request-time external and database operations. Never block
  the event loop with long-running work.
- Prefer Direct Play, then remux. Transcoding is future, opt-in functionality;
  never start FFmpeg automatically.
- Backend: Python 3.12+, complete type hints, PEP 8, Ruff, explicit exception
  handling, structured logs, and no silently swallowed failures.
- Frontend: Vue 3 Composition API, strict TypeScript, reusable components and
  composables, Pinia, Vue Router, API calls in a dedicated service, and avoid
  `any`.
- Database: SQLAlchemy, Alembic migrations, foreign keys, controlled
  transactions, indexes for frequent queries, and SQLite WAL only on a suitable
  local filesystem. Database data must persist outside the container.
- Version REST endpoints under `/api/v1`, retain OpenAPI documentation, validate
  all input, and return a consistent error shape.
- Keep secrets server-side and out of Git, frontend bundles, logs, and error
  responses. Never log passwords, tokens, or API keys.
- Keep resource use modest for the target i5-2500K/8 GB host. Avoid high-rate
  polling and unbounded concurrency.

## Testing and documentation

- Backend tests use Pytest; frontend tests use Vitest; future browser E2E tests
  use Playwright.
- Every implemented feature needs observable, executable behavior and tests
  proportionate to its risk.
- Streaming and storage safety require the complete dedicated test matrices in
  the specification when those stages begin; do not claim them in Stage 1.
- Keep `README.md`, `docs/architecture.md`, `docs/deployment.md`, `docs/api.md`,
  `docs/streaming.md`, `docs/storage.md`, and `docs/troubleshooting.md` current.

