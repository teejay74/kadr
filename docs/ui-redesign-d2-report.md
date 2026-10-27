# UI redesign D2 report

## Completed work

- Added a dedicated responsive `/downloads` page and top-level navigation.
- Moved torrent state, progress, transfer speed, peers/seeds, pause/resume,
  on-demand file inspection, and protected completed-file deletion away from
  film and series pages.
- Added a bounded backend task-list endpoint. It reads at most 100 recent KADR
  tasks and joins them with one qBittorrent list request.
- Represents database tasks missing from qBittorrent as unavailable with all
  mutating controls disabled.
- Polls every ten seconds only while an incomplete task is active; file lists
  load only after an explicit user action.
- Removed the legacy technical panel from media-page rendering. Its component
  and tests remain in the repository for rollback until real playback checks
  on Debian are complete.
- Kept the unified SourceSelector, Episode Matcher, Playback Resolver,
  Streaming Manager, Direct Play, library persistence, Photodom, Debian
  configuration, and production user data unchanged.

## Changed files

Backend:

- `backend/app/api/v1/torrents.py`
- `backend/app/repositories/torrent_tasks.py`
- `backend/app/services/torrents/manager.py`
- `backend/tests/test_torrents.py`

Frontend:

- `frontend/src/layouts/AppShell.vue`
- `frontend/src/pages/DownloadsPage.vue`
- `frontend/src/pages/DownloadsPage.test.ts`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/pages/MediaDetailsPage.test.ts`
- `frontend/src/router/index.ts`
- `frontend/src/services/api.ts`
- `frontend/src/services/api.test.ts`
- `frontend/src/styles/main.css`

Documentation:

- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/troubleshooting.md`
- This report.

## Checks and test results

- Dedicated backend torrent tests: `16 passed`.
- Dedicated frontend downloads/details/API tests: `27 passed`.
- Strict Vue TypeScript and Vite production build: passed.
- Fresh backend image and full Pytest suite: `118 passed`.
- Ruff over backend application, migrations, and tests: passed.
- Fresh frontend image and full Vitest suite: `67 passed` across 13 files.
- Docker Compose configuration validation: passed.
- Disposable SQLite upgraded through `0006_episode_matcher`; Alembic reported
  `No new upgrade operations detected`.
- `git diff --check`: passed.

## Known limitations

- There is no whole-task deletion endpoint. D2 deliberately reuses protected
  individual completed-file deletion and does not broaden destructive scope.
- Missing qBittorrent tasks remain visible as unavailable history; automatic
  database pruning is outside this UI stage.
- Browser E2E against real Prowlarr, qBittorrent, Direct Play, saved library
  files, and the Debian host is still required before deleting legacy
  `SourcesPanel` source code.

## Completion and next actions

- D2 is complete and locally verified.
- Perform live film, series, next-episode, Downloads, and library acceptance on
  the isolated KADR Debian deployment when separately authorized.
- Remove legacy `SourcesPanel` only after those live checks pass.
