# Audio and subtitle tracks D3.1 report

## Completed work

- Added on-demand audio and subtitle discovery for the currently selected
  torrent file and for an explicit saved-library item.
- Added bounded asynchronous `ffprobe` execution with a configurable timeout,
  exact argv invocation without a shell, controlled errors, and a small
  process-local cache keyed by canonical path, size, and modification time.
- Required a selected torrent file to be fully downloaded before probing. The
  service does not trigger downloads and does not scan other files or seasons.
- Added normalized track metadata: opaque exact ID, semantic preference key,
  stream index, language, codec, optional title, default/forced/hearing-impaired
  flags, and audio channel metadata.
- Kept exact stream identity separate from semantic preference identity so a
  later stage can restore language/studio choices without relying only on a
  numeric stream index.
- Classified text subtitles as future external-WebVTT candidates, bitmap
  subtitles as explicit burn-in candidates, and unknown codecs as unsupported.
- Sanitized and length-limited untrusted ffprobe language/title metadata and
  retained `null` for absent titles or unknown languages.
- Preserved Direct Play, HTTP Range behavior, compatibility artifacts, and
  current FFmpeg start rules. Track discovery never starts FFmpeg.

## API

- `GET /api/v1/torrents/{task_id}/tracks`
- `GET /api/v1/library/{item_id}/tracks`

Probe failures return `409 playback_tracks_unavailable`. Existing path and
entity errors keep their established response codes.

## Changed files

Backend:

- `backend/app/api/dependencies.py`
- `backend/app/api/v1/library.py`
- `backend/app/api/v1/torrents.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/schemas/playback.py`
- `backend/app/services/playback/exceptions.py`
- `backend/app/services/playback/tracks.py`
- `backend/tests/test_playback_tracks.py`

Configuration and documentation:

- `.env.example`
- `docker-compose.yml`
- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/streaming.md`
- `docs/troubleshooting.md`
- This report.

The same working tree also contains the already verified D2.1 stabilization
files documented separately in `docs/ui-redesign-d2-1-report.md`.

## Checks and test results

- Dedicated D3.1 track tests: `6 passed`.
- Focused track/resolver/streaming regression set: `32 passed`.
- Full backend Pytest suite: `125 passed`.
- Ruff over the complete backend tree: passed.
- Fresh disposable SQLite migration chain through `0006_episode_matcher`:
  passed during every backend container run; D3.1 needs no schema migration.
- Docker Compose configuration: passed.
- `git diff --check`: passed.

## Known limitations

- The Vue player menu and client-side selection are not part of D3.1.
- Track probing waits for one selected torrent file to finish downloading.
  Partial-file probing is intentionally avoided because container metadata can
  be incomplete or misleading.
- D3.1 classifies subtitle delivery but does not yet convert text subtitles to
  WebVTT or burn bitmap subtitles into video.
- Browser-native switching remains browser/container dependent. MKV alternate
  audio cannot be assumed to work through HTML media APIs.
- The existing compatible mode still uses the first audio track. An explicit
  selected-audio pipeline belongs to a later substage and must preserve the
  current position when changing stream URLs.
- The in-process cache is deliberately lost on restart; discovery is cheap and
  preference persistence is a separate stage.

## Completion and next actions

- D3.1 Track Discovery API is complete and locally verified.
- D3.2 should add persistent semantic language/track preferences and selection
  resolution before the player menu depends on them.
- D3.3 can then expose explicit compatible audio/subtitle delivery and restore
  playback position after a stream switch. It must not start FFmpeg during
  ordinary Direct Play.

