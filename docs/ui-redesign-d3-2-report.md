# Audio and subtitle tracks D3.2 report

## Completed work

- Added profile-scoped persistent audio and subtitle preferences.
- Stored semantic track identity plus normalized language, optional title, and
  codec without persisting a numeric stream index as the preference.
- Added deterministic resolution for reordered streams: semantic key first,
  then language/title/codec fallbacks, then the file default or first track.
- Kept subtitle enablement explicit and retained the last subtitle semantics
  while subtitles are turned off.
- Extended torrent and library track responses with exact resolved IDs for the
  current file.
- Added PUT endpoints that validate selected opaque IDs against the probed file
  before saving them. Cross-file or stale IDs are rejected.
- Added migration `0007_playback_track_preferences` without rewriting existing
  library, history, episode, or torrent data.
- Kept Direct Play, Range streaming, compatibility artifacts, and FFmpeg start
  behavior unchanged.

## API

- `GET /api/v1/torrents/{task_id}/tracks?profile_key=default`
- `PUT /api/v1/torrents/{task_id}/tracks/preferences`
- `GET /api/v1/library/{item_id}/tracks?profile_key=default`
- `PUT /api/v1/library/{item_id}/tracks/preferences`

Preference writes accept `profile_key`, `audio_track_id`,
`subtitle_track_id`, and `subtitles_enabled`. Invalid current-file selections
return `422 invalid_playback_track`.

## Changed files

Backend and migration:

- `backend/app/api/dependencies.py`
- `backend/app/api/v1/library.py`
- `backend/app/api/v1/torrents.py`
- `backend/app/main.py`
- `backend/app/models/__init__.py`
- `backend/app/models/playback.py`
- `backend/app/repositories/playback.py`
- `backend/app/schemas/playback.py`
- `backend/app/services/playback/exceptions.py`
- `backend/app/services/playback/tracks.py`
- `backend/migrations/versions/0007_playback_track_preferences.py`
- `backend/tests/test_playback_tracks.py`
- `backend/tests/test_playback_track_preferences.py`

Documentation:

- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/storage.md`
- `docs/streaming.md`
- This report.

## Checks and test results

- Focused preference, track API, and migration tests: `9 passed`.
- Ruff on the rebuilt D3.2 backend image: passed.
- Full backend Pytest suite: `128 passed`.
- A real SQLite migration test upgrades a populated `0006` database to `0007`,
  verifies the existing row, independent profiles, and unique profile keys.
- `alembic check`: no missing model/schema operations.
- Docker Compose configuration and `git diff --check`: passed.

## Known limitations

- The current Vue player does not yet expose the track menu.
- Persisting a preference does not itself switch a browser media stream.
- Files with several same-language tracks and no distinguishing title/codec
  metadata can only fall back to their default/first stream when the exact
  semantic key differs.
- Text subtitle conversion, bitmap burn-in, and selected-audio compatible
  streams remain later explicit stages.

## Completion and next actions

- D3.2 is ready for the full backend regression run.
- D3.3 should add the KadrPlayer menu and use browser-native track APIs only
  where the browser exposes them reliably.
- Explicit derived streams must preserve playback position and must never start
  FFmpeg during ordinary Direct Play.

