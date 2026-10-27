# UI redesign report — substage B2

Date: 2026-10-27

## Completed work

- Added persistent logical episode identity, independent of torrent tasks and
  physical files.
- Added torrent file variants and many-to-many episode/file bindings. One task
  can retain different `file_id` values for several episodes, and one episode
  can retain several variants.
- Preserved `torrent_tasks.selected_file_id` and `selected_file_path` as the
  backward-compatible active playback selection.
- Extended file selection so an explicitly selected series file can be bound
  to season/episode/provider identity without exposing a filesystem path.
- Made library records episode-aware and retained their physical `file_id`.
  Cache deletion now protects the exact saved task/file, while whole-task cache
  cleanup protects any task referenced by the library.
- Made watch history independent by logical episode and `profile_key`, with
  `default` retaining the existing single-profile behavior.
- Added SQLite partial unique indexes for title-level nullable episode keys and
  episode-level keys. The migration preserves legacy library/history rows,
  defaults old history to profile `default`, and backfills saved `file_id` values
  from the legacy selected file when available.
- Updated the retained `SourcesPanel` to persist bindings after explicit file
  selection. The player and library use episode identity only when the current
  selected file has that exact persisted binding, preventing a restored legacy
  file from being attributed to the wrong episode.
- Added per-episode browser resume keys and episode-aware server history calls.
- Kept the legacy source and playback workflow available; it was not deleted or
  replaced in B2.

## Changed files

Backend application and migration:

- `backend/app/api/dependencies.py`
- `backend/app/api/v1/library.py`
- `backend/app/api/v1/torrents.py`
- `backend/app/models/__init__.py`
- `backend/app/models/episodes.py`
- `backend/app/models/library.py`
- `backend/app/repositories/episodes.py`
- `backend/app/repositories/library.py`
- `backend/app/schemas/library.py`
- `backend/app/schemas/torrents.py`
- `backend/app/services/cache/manager.py`
- `backend/app/services/library/manager.py`
- `backend/app/services/torrents/manager.py`
- `backend/migrations/versions/0004_library.py` (format-only cleanup)
- `backend/migrations/versions/0005_episode_persistence.py`

Backend tests:

- `backend/tests/test_episode_persistence.py`
- `backend/tests/test_torrents.py`

Frontend:

- `frontend/src/components/KadrPlayer.vue`
- `frontend/src/components/SourcesPanel.vue`
- `frontend/src/components/SourcesPanel.test.ts`
- `frontend/src/pages/LibraryPage.test.ts`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/services/api.ts`
- `frontend/src/services/api.test.ts`
- `frontend/src/types/media.ts`

Documentation:

- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/storage.md`
- `docs/troubleshooting.md`
- This report.

## Checks and results

- Fresh backend test image and full Pytest suite: `85 passed`.
- The backend suite upgraded a disposable database through migration `0005`.
- A dedicated migration test created a real `0004` SQLite database, inserted
  legacy library/history data, upgraded it to `0005`, verified preservation and
  backfill, and exercised nullable partial-unique behavior.
- `alembic check`: no model/schema upgrade operations missing.
- Ruff over the backend application, migrations, and tests: passed.
- Fresh frontend image, strict Vue TypeScript check, and Vite production build:
  passed.
- Full frontend Vitest suite: `43 passed` across 9 files.
- Docker Compose configuration: validated after implementation.
- The production stack and Debian host were not changed in B2, so no live
  service-health or server-log claim is made here.

## Known limitations

- B2 supplies persistence and compatibility plumbing, not the unified playback
  resolver. An episode card still hands off to the retained source panel.
- The backend does not yet determine the next episode or cross-season
  transition. The frontend must not infer it by incrementing the episode
  number; this belongs to the next resolver stage.
- Existing manual prefetch controls remain available. Automatic near-end
  prebuffering of exactly one backend-resolved next episode is deferred until
  next-episode resolution exists. No new automatic whole-season download was
  added.
- `profile_key` provides persistence isolation, but KADR does not yet have an
  authenticated profile-management UI; callers use `default` unless they
  explicitly supply another key.
- Legacy tasks without persisted bindings remain playable, but their resume
  state stays title/task-level until a file is explicitly bound. KADR does not
  guess identity from a restored file name.
- Downgrading to `0004` after creating multiple episode rows for one title may
  violate the older media-level unique constraints. Operational rollback must
  restore the pre-B2 online SQLite backup instead of relying on downgrade.
- Full browser E2E playback against qBittorrent and the Debian production host
  remains an acceptance check after a separately approved deployment.

## Readiness for the next substage

B2 is complete and locally verified. The database can now represent logical
episodes, multiple file variants, multi-file torrent tasks, episode library
items, and profile-aware episode history without deleting legacy data. The next
substage may implement a backend playback resolver and backend-owned
next-episode navigation, while retaining `SourcesPanel` until movie, series,
and library playback pass end-to-end checks.
