# Season download and whole-task deletion report

Date: 2026-10-30

## Completed work

- Added «Скачать сезон» beside the active season selector on the current series
  details page.
- Reused the normalized source selector and Episode Matcher. Only confirmed,
  safe video files belonging to the selected season are queued; the first
  episode becomes the active selection and remaining files use the existing
  bounded prefetch endpoint.
- Added a whole-download action to every Downloads card with a required second
  confirmation and the currently downloaded size in the confirmation label.
- Added `DELETE /api/v1/torrents/{task_id}`. The cache service protects active
  streams, running or queued compatibility work, saved library items, and paths
  outside the configured KADR storage root.
- Whole-task deletion asks qBittorrent to remove torrent data, removes
  task-scoped playback artifacts, and deletes the database task with cascading
  episode/file bindings.

## Changed files

- Backend torrent API, cache/playback services, schemas, and cache tests.
- Frontend media details, source selector, Downloads page, API client, types,
  styles, and component/API tests.
- `README.md`, `docs/api.md`, `docs/architecture.md`, `docs/storage.md`, and
  `docs/troubleshooting.md`.

## Checks and test results

- Targeted backend suite: 28 passed.
- Targeted frontend suite: 35 passed.
- Full backend suite: 143 passed.
- Full frontend suite: 82 passed.
- Ruff, strict TypeScript, production frontend build, and Compose model
  validation passed.
- `docker compose ps` and bounded service-log inspection completed without
  changing service state. No local KADR services were running, so runtime health
  could not be asserted in this workspace.

## Deployment

- Feature commit `52a94a5e3870267cb07ea79e8c9472c731ed2735` was pushed to
  `origin/main` and deployed to the Debian host on 2026-10-30.
- The pre-deployment audit confirmed separate KADR and Photodom Compose
  projects, networks, storage paths, databases, and published ports.
- A database backup was created at
  `/srv/kadr/backups/kadr-pre-52a94a5-20261030-113715.db`; SQLite integrity
  validation returned `ok`.
- The exact server checkout passed 143 backend tests, 82 frontend tests, Ruff,
  strict TypeScript, and the production frontend build.
- Only the KADR `api` and `web` services were rebuilt and recreated. Both were
  healthy after deployment; the API health endpoint reported an `ok` database,
  the web entry point returned HTTP 200, and Alembic reported
  `0007_playback_track_preferences (head)`.
- qBittorrent, Prowlarr, FlareSolverr, and Photodom were not restarted or
  modified. Their existing containers remained healthy.

## Known issues

- Season download depends on filenames/metadata that Episode Matcher can
  confirm. Ambiguous mappings require user confirmation; unrecognized releases
  are not force-enabled.
- `reclaimed_bytes` is qBittorrent's best available downloaded-byte estimate,
  not a post-deletion filesystem measurement.

## Next actions

- Perform one user-authorized end-to-end season queue and one disposable
  whole-task deletion as a destructive production smoke test when suitable test
  media is available.
