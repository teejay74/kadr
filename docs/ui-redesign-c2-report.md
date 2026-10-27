# UI redesign report — substage C2

Date: 2026-10-27

## Completed work

- Added a modal `SourceSelector` to the unified movie/episode playback flow.
- Opened the modal only for backend `source_required`/`unavailable` states or
  the explicit “Другой источник” action in the media actions menu.
- Displayed normalized quality, release type, size, language/audio, and seed
  count without exposing the raw torrent release name in the main list.
- Kept raw release title and indexer behind “Технические подробности”.
- Added a conservative convenience recommendation based on normalized quality,
  source type, and availability, with an explicit non-guarantee notice.
- Added the selected release through the existing opaque source-ID API and
  bounded torrent-metadata polling; no credentials or magnet links reach the
  browser.
- Kept concrete movie-file selection on the backend. For a new film source,
  Torrent Manager selects the largest safe supported video and the unified
  resolver performs normal piece-readiness checks.
- Ran selected series sources through Episode Matcher. Unique exact mappings
  continue directly to the shared player; ambiguous mappings open the
  confirmation dialog and are persisted before resolver retry.
- Kept the legacy `SourcesPanel` mounted and unchanged as the regression/manual
  fallback required by the rollout plan.
- Did not change Streaming Manager, Direct Play, FFmpeg activation, Photodom,
  Debian configuration, or production user data.

## Changed files

Backend C2 additions:

- `backend/app/services/playback/resolver.py`
- `backend/app/services/torrents/manager.py`
- `backend/tests/test_playback_resolver.py`
- `backend/tests/test_torrents.py`

Frontend C2 additions:

- `frontend/src/components/MediaActions.vue`
- `frontend/src/components/SourceSelector.vue`
- `frontend/src/components/SourceSelector.test.ts`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/pages/MediaDetailsPage.test.ts`
- `frontend/src/styles/main.css`

Documentation:

- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/troubleshooting.md`
- This report.

Episode Matcher files in the same uncommitted working stage are listed in
`docs/ui-redesign-episode-matcher-report.md`.

## Checks and results

- Docker Compose configuration validation: passed.
- Fresh backend test image and full Pytest suite: `112 passed`.
- Ruff over backend application, migrations, and tests: passed.
- Fresh frontend image, strict Vue TypeScript check, and Vite production build:
  passed.
- Full frontend Vitest suite: `58 passed` across 11 files.
- Dedicated C2 tests cover normalized source presentation, hidden technical
  details, recommendation disclaimer, modal source choice, automatic movie
  resolver retry, series ambiguity handoff to Episode Matcher, backend movie
  file choice, and unsafe larger-file exclusion.
- The disposable backend database upgraded through
  `0006_episode_matcher` before tests.
- No production stack or Debian host was changed, so this report does not claim
  live playback acceptance.

## Known limitations

- Torrent metadata waiting in the modal is deliberately bounded. Slow magnets
  may require the user to retry after qBittorrent receives the file list.
- The movie default is the largest safe supported video. It is a backend-owned
  deterministic MVP policy, not media-content analysis; the retained legacy
  panel can correct unusual releases containing a larger bonus video.
- Recommendation is not a health guarantee and does not persist per-profile
  quality preferences yet.
- Source selection is not yet covered by browser E2E against real Prowlarr,
  qBittorrent, Direct Play, and the Debian host.
- Legacy `SourcesPanel` remains visible until film, series, and library
  playback pass the required end-to-end checks.
- Next-episode/cross-season resolution and near-end prebuffering remain a
  separate backend-owned substage; C2 does not increment episode numbers in the
  frontend or start season-wide automatic downloads.

## Readiness for the next substage

C2 is complete and locally verified. The next substage can implement
backend-owned next-episode resolution, the player transition overlay, and
bounded prebuffering of exactly the resolved next episode. It must add new
tests before any later stage and must retain the legacy source panel until live
playback acceptance is complete.
