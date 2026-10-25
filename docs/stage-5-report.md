# Stage 5 report — Streaming MVP

Date: 2026-10-24

This report records the original Direct Play delivery. The explicit FFmpeg
compatibility extension completed on 2026-10-25 is documented separately in
[stage-5-compatibility-report.md](stage-5-compatibility-report.md).

## Completed

- Added an availability-aware Streaming Manager with canonical path checks,
  configurable buffering, bounded waits, and concurrent-session accounting.
- Added single-range HTTP delivery with correct `200`, `206`, `416`,
  `Accept-Ranges`, `Content-Length`, and `Content-Range` behavior.
- Added qBittorrent torrent-properties and piece-state adapter calls. Bytes are
  read only after every intersecting torrent piece is complete.
- Added qBittorrent sequential-download and first/last-piece hints for new and
  existing incomplete streams, plus a dedicated unbuffered nginx streaming
  route whose timeout exceeds the API's configurable wait ceiling.
- Selected video files use normal rather than maximal qBittorrent priority so
  sequential piece ordering begins at the requested range on qBittorrent 5.x.
- Initial buffering adapts to observed speed and treats the configured 32 MiB
  value as a cap instead of a hard minimum.
- Parallel browser Range requests for one torrent task share an active-stream
  slot and are separately bounded, avoiding false `429` responses from one
  native video element.
- Added a responsive native HTML5 Direct Play player with explicit activation,
  buffering/error states, close/disconnect cleanup, seeking, fullscreen and
  standard media controls.
- Added network/decode/unsupported-format error messages, a fresh-request retry
  action, and non-destructive source switching.
- Added a startup-readiness endpoint and five-second frontend polling. The
  player now waits for both the adaptive initial buffer and container tail before
  attaching the video source, so a preparation timeout is not misreported as a
  codec error.
- Reopening an already registered torrent now bypasses the new-download
  concurrency gate; the limit still applies before KADR creates a new task.
- Added browser-local resume position with an explicit continue/restart choice.
- Added backend and frontend coverage for range parsing, full/partial streams,
  seeks, incomplete pieces, slow/missing data, disconnect/reconnect,
  concurrent limits, UI activation, resume, and errors.
- Updated repository, architecture, API, deployment, streaming, and
  troubleshooting documentation.

## Changed files

- Runtime configuration: `.env.example`, `docker-compose.yml`.
- Backend: `backend/app/core/config.py`, `backend/app/main.py`,
  `backend/app/api/dependencies.py`, `backend/app/api/v1/router.py`,
  `backend/app/api/v1/streaming.py`,
  `backend/app/services/torrents/qbittorrent.py`, and the new
  `backend/app/services/streaming/` package.
- Backend tests: `backend/tests/test_streaming.py`.
- Frontend: `frontend/src/components/SourcesPanel.vue`,
  `frontend/src/components/KadrPlayer.vue`, and
  `frontend/src/styles/main.css`.
- Frontend tests: `frontend/src/components/KadrPlayer.test.ts`.
- Documentation: `README.md`, `docs/api.md`, `docs/architecture.md`,
  `docs/deployment.md`, `docs/streaming.md`, `docs/troubleshooting.md`, and
  this report.

## Verification

- Backend: `39 passed` with Pytest.
- Frontend: `14 passed` across 5 Vitest files.
- Production frontend TypeScript/Vite build: passed.
- Ruff: passed.
- Compose configuration: valid; all four services healthy after rebuild.
- Live health through nginx: `200` with the SQLite check reported as `ok`.
- OpenAPI exposes `/api/v1/torrents/{task_id}/stream` and its readiness check.
- Live range acceptance used the existing Creative Commons Sintel fixture while
  it was still incomplete: `bytes=0-1023` returned `206`, exactly 1024 bytes,
  `video/mp4`, and `Content-Range: bytes 0-1023/129241752`. An out-of-bounds
  request returned `416` and `Content-Range: bytes */129241752`.
- The acceptance torrent was explicitly returned to `stoppedDL`; no test data
  was deleted.
- API/web logs showed normal startup and expected `200`, `206`, and `416`
  requests, with no application errors.
- Regression verification on the previously timing-out 6.3 GiB MKV returned
  `206`, `Content-Type: video/x-matroska`, and the exact requested 1024 bytes
  through nginx after the streaming-mode and MIME fixes.
- A browser-compatible MP4 release was identified as H.264 High + HE-AAC with
  `ffprobe`. Its readiness endpoint reached `ready: true`, the first MiB
  returned `206 video/mp4`, and headless Chrome opened it with normal `200` and
  follow-up `206` media ranges and no API error responses.

## Known limitations

- Direct Play depends on browser support for the selected container and codecs.
- qBittorrent's Web API cannot assign priority to an arbitrary piece range.
  KADR enables sequential and first/last-piece modes, assigns normal priority
  to the selected file, and safely times out if a distant seek range does not
  arrive; optimized arbitrary seek scheduling needs another torrent adapter.
- A timeout after HTTP response headers have already been sent closes the media
  response; the browser displays the controlled player error rather than an API
  JSON body.
- Resume state is browser-local until Stage 6 adds persisted watch history.
- Remux and bounded transcoding are now available only through the explicit
  compatibility action described in the extension report. Media deletion,
  library management, and remote access are not implemented.

## Next action

Stage 6 can add the media library, saved-content protection, cache lifecycle,
watch history, and favorites. Its deletion paths require the complete storage
safety matrix before any destructive behavior is enabled.
