# Stage 5 extension report — compatible playback

Date: 2026-10-25

## Completed

- Added `ffprobe` inspection and explicit FFmpeg preparation without changing
  the Direct Play-first path.
- Added three strategies: MP4 remux, audio-only AAC conversion, and bounded
  H.264/AAC conversion for incompatible video.
- Added progress/status and byte-range streaming endpoints for generated MP4.
- Added a frontend “Совместимая версия” action, progress UI, error handling,
  and automatic switch to the prepared stream.
- Kept torrent downloads read-only in the API and isolated generated output in
  `data/playback`, using temporary files and atomic completion.
- Added a free-space reserve, one-job concurrency limit, two-thread encoder
  default, 1080p ceiling, unprivileged execution, and container resources.
- Added backend strategy/range tests and frontend preparation/playback tests.
- Corrected the active-download gate so completed seeding torrents do not
  prevent adding another source; incomplete queued or stalled downloads remain
  bounded.
- Replaced the technical torrent controls with a guided three-step flow:
  release selection, one-click video/episode selection plus download, and
  playback. Metadata and progress now refresh automatically every five seconds;
  compatibility preparation is tucked behind contextual help. The latest task
  is restored from the API after a page reload, while an explicit return to the
  release list is remembered in the browser.
- Fixed playback-slot cleanup when a browser rejects or abandons a stream.
  Direct Play and its compatible fallback now share one viewer slot, completed
  compatible artifacts are reused automatically, and nginx streams both paths
  without proxy buffering.
- Updated API, architecture, deployment, storage, streaming, and
  troubleshooting documentation.

## Changed files

- Runtime: `backend/Dockerfile`, `docker-compose.yml`, `.env.example`,
  `.gitignore`, `data/playback/.gitkeep`.
- Backend: `backend/app/services/playback/`,
  `backend/app/api/v1/playback.py`, `backend/app/schemas/playback.py`, plus API
  dependencies, routing, configuration, lifecycle, and error handlers.
- Frontend: `frontend/src/components/KadrPlayer.vue`, API/types, styles, and
  player tests.
- Tests: `backend/tests/test_playback.py` and the existing streaming/torrent
  regression suites.
- Documentation: `README.md`, `docs/api.md`, `docs/architecture.md`,
  `docs/deployment.md`, `docs/storage.md`, `docs/streaming.md`,
  `docs/troubleshooting.md`, and this report.

## Verification

- Backend Pytest: 45 passed.
- Frontend Vitest: 19 passed across 5 files.
- Ruff: passed with cache disabled in the read-only test container.
- Vue strict TypeScript and production Vite build: passed.
- Docker Compose configuration: valid.
- Runtime image contains FFmpeg and `ffprobe` 5.1.9.
- Live API/web health passed after rebuild. An existing complete 3.5 GB MKV
  was probed as H.264 + AC3 and correctly selected `audio_transcode` rather
  than re-encoding video.
- The generated 3.1 GB MP4 probed as H.264 High/yuv420p plus AAC-LC stereo.
- FFmpeg decoded the first 10 seconds of the generated AAC track without an
  error, and the ready artifact remained discoverable after an API restart.
- `bytes=0-1023` on the compatible stream returned `206 video/mp4`, exact
  `Content-Length: 1024`, and
  `Content-Range: bytes 0-1023/3292340699`.

## Known limitations

- Preparation starts only after the selected file reaches 100%; it is not
  live/on-the-fly transcoding.
- Full video conversion is CPU-intensive and must be validated on the target
  Debian host before deployment.
- Only the first audio stream is retained and converted to AAC-LC stereo.
  Alternate audio selection and embedded subtitles are future work.
- HDR tone mapping is not implemented. Full conversion normalizes the pixel
  format but does not promise correct HDR-to-SDR appearance.
- Generated artifacts have no deletion UI yet and remain in the isolated cache
  until a later reviewed lifecycle implementation.
