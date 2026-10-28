# UI redesign D3.4 report

## Completed work

- Added the explicit `audio_track` compatible-playback mode for completed
  selected torrent files.
- Revalidated the opaque audio-track ID against a fresh bounded probe before
  starting FFmpeg; stale and cross-file IDs are rejected.
- Mapped the exact selected global stream, copied video, and converted only
  that audio stream to AAC stereo.
- Isolated generated artifacts and active jobs by track identity so different
  choices cannot reuse one another's output.
- Added the KadrPlayer action «Подготовить выбранную аудиодорожку» only when
  native browser switching is unavailable.
- Preserved and restored the playback position when changing to the prepared
  compatible stream.
- Kept Direct Play unchanged: saving a preference and ordinary playback do not
  start FFmpeg.

## Changed areas

- Backend playback schemas, API, dependency wiring, preparation service, and
  Compatibility Manager.
- Frontend API/types and KadrPlayer compatible-audio workflow.
- Backend and frontend playback tests.
- README and API, architecture, streaming, and troubleshooting documentation.

## Checks and test results

- Backend full suite: `131 passed`.
- Frontend full suite: `72 passed` in 13 test files.
- Focused Backend D3.4 suite: `17 passed`.
- Focused Frontend D3.4 suite: `36 passed`.
- Frontend production build and TypeScript type check: passed.
- Ruff: passed.

## Known limitations

- Selected-audio compatible preparation is currently available only for a
  completed torrent source, not a saved library item.
- Video is copied rather than transcoded in this mode. If the browser cannot
  decode the video codec, the viewer must use full compatibility preparation.
- Subtitle extraction/delivery and explicit bitmap burn-in are not part of
  this increment.
- The prepared MP4 contains the selected audio rendition, not every original
  audio stream.

## Next actions

- Implement explicit delivery of text subtitles as WebVTT after selection,
  with track revalidation and position preservation.
- Keep bitmap subtitle burn-in as a separate explicit compatibility path.
- Add saved-library compatible-track support without weakening library path
  and active-stream protections.
