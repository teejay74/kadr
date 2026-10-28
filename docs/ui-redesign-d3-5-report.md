# UI redesign D3.5 report

## Completed work

- Added explicit WebVTT preparation for one selected text subtitle from a
  completed torrent file or saved library item.
- Re-probed the source and validated the opaque track ID and delivery class
  before invoking FFmpeg.
- Mapped only the exact subtitle stream and published output atomically under
  the isolated playback cache.
- Cached artifacts by source fingerprint and track identity and bounded both
  extraction time and concurrency.
- Added the KadrPlayer «Подготовить выбранные субтитры» action, same-origin
  `<track>` attachment, and playback-position restoration.
- Kept track discovery, preference persistence, Direct Play, and HTTP Range
  behavior free of automatic FFmpeg work.

## Changed areas

- Backend settings, playback schema/exceptions, Subtitle Manager, track
  service, dependency wiring, and torrent/library routes.
- Frontend playback types/API and KadrPlayer subtitle workflow.
- Compose/environment configuration and playback documentation.
- Dedicated Backend and Frontend tests.

## Checks and test results

- Backend full suite: `133 passed`.
- Frontend full suite: `74 passed` in 13 test files.
- Focused Backend playback/subtitle suite: `19 passed`.
- Focused Frontend player/API suite: `38 passed`.
- Frontend production build and TypeScript type check: passed.
- Ruff: passed.

## Known limitations

- Bitmap PGS/DVD/DVB subtitle tracks are not rendered. They remain classified
  as `burn_in_required` for a later explicit video-compatible path.
- ASS/SSA styling is flattened to the WebVTT capabilities supported by the
  browser; complex positioning and fonts may not be preserved.
- WebVTT extraction parses the selected completed file on first request and is
  not intended for partially downloaded torrent files.
- Generated subtitle cache cleanup is not yet independently exposed in the UI;
  it remains inside KADR's isolated playback cache.

## Next actions

- Design and implement explicit bitmap subtitle burn-in without changing
  ordinary Direct Play.
- Extend compatible selected-audio preparation to saved library items.
- Validate audio/subtitle switching with real MKV samples in Debian acceptance.
