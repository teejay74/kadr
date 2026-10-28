# Compatible playback preparation queue report

Date: 2026-10-28 (Asia/Yekaterinburg).

## Completed work

- Replaced immediate rejection of a second compatible-playback preparation
  with a bounded process-local FIFO queue.
- Kept the conservative default of one active FFmpeg process and two video
  encoder threads.
- Added idempotent reuse of an identical active or queued request.
- Added automatic dispatch of the next queued job after success or failure of
  the active task.
- Added queue position to the API and player, plus explicit cancellation for a
  job that has not started.
- Included active and queued source sizes in the playback-cache free-space
  gate so waiting work cannot silently overcommit storage.
- Retained the earlier source-task recovery fix for duplicate torrents whose
  Prowlarr result does not include an info hash.

## Changed files

- Backend configuration, playback schemas, API, manager, service, exceptions,
  torrent repository/manager, and tests.
- Frontend API/types, player UI, and tests.
- Compose/environment examples and API, streaming, architecture, and
  troubleshooting documentation.

## Checks

- Rebuilt the backend and frontend test images from the exact working tree.
- Ran the complete backend Pytest suite.
- Ran the complete frontend Vitest suite and production build.
- Ran Ruff, Vue/TypeScript type checking, Compose validation, and
  `git diff --check`.

## Test results

- Backend: 138 passed.
- Frontend: 76 passed.
- Ruff: passed.
- Vue/TypeScript type check: passed.
- Frontend production build: passed.
- Docker Compose configuration: passed.

## Debian deployment acceptance

- Deployed code commit `bc4bca57ca77bababd8a95b046ea51ccaa2236fc` to
  the isolated `/srv/kadr` checkout.
- Created and verified the online SQLite backup
  `/srv/kadr/backups/kadr-pre-playback-queue-20261028-142207.db` before the
  deployment (`PRAGMA integrity_check`: `ok`).
- Re-ran the complete backend and frontend test suites, Ruff, the
  Vue/TypeScript type check, and the frontend production build on Debian.
- Rebuilt and recreated only the KADR `api` and `web` services. qBittorrent,
  Prowlarr, FlareSolverr, and Photodom were not restarted.
- Confirmed healthy API and web containers, an `ok` API/database health
  response, Alembic revision `0007_playback_track_preferences`, and effective
  queue limits of one active plus five waiting jobs.
- Confirmed that Photodom and the unchanged KADR integration services remained
  healthy after deployment.

## Known issues

- Waiting jobs are intentionally process-local and disappear when the API
  restarts. Completed compatible artifacts remain on disk and are reused.
- FIFO ordering has no background/manual priority classes because KADR does not
  yet enqueue compatibility preparation automatically.
- Only waiting jobs can be cancelled; stopping a running FFmpeg process is not
  exposed to the client.

## Next actions

1. On Debian, queue compatibility preparation for two fully downloaded
   episodes and verify that the second starts automatically.
2. Observe CPU, memory, playback-cache space, and Photodom health while keeping
   `KADR_MAX_ACTIVE_TRANSCODES=1`.
