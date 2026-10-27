# UI redesign D1 report

## Completed work

- Added backend-owned next-episode discovery from TMDB episode lists instead
  of frontend number arithmetic, including transitions between seasons.
- Added a next-episode resolution endpoint that prefers the current torrent
  task while still using the unified library/torrent Playback Resolver.
- Added opportunistic near-end prefetch for exactly one confirmed next file.
  The selected current file remains enabled and no season-wide queue is
  created by this flow.
- Detects a shared combined file and declines to promise a precise transition
  to a later logical episode without stored time boundaries.
- Added `NextEpisodeOverlay` with explicit play, a persisted opt-in autoplay
  preference, five-second visible countdown, end-of-series and controlled
  unavailable states. A next episode without a binding opens the normal source
  selector instead of attempting frontend file inference.
- Kept legacy `SourcesPanel`, Streaming Manager, Direct Play, Photodom, Debian
  configuration, and production user data unchanged.

## Changed files

Backend D1 additions:

- `backend/app/api/dependencies.py`
- `backend/app/api/v1/playback.py`
- `backend/app/schemas/playback.py`
- `backend/app/services/playback/navigation.py`
- `backend/app/services/playback/resolver.py`
- `backend/tests/test_episode_navigation.py`

Frontend D1 additions:

- `frontend/src/components/KadrPlayer.vue`
- `frontend/src/components/KadrPlayer.test.ts`
- `frontend/src/components/NextEpisodeOverlay.vue`
- `frontend/src/components/NextEpisodeOverlay.test.ts`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/pages/MediaDetailsPage.test.ts`
- `frontend/src/services/api.ts`
- `frontend/src/services/api.test.ts`
- `frontend/src/styles/main.css`
- `frontend/src/types/media.ts`

Documentation:

- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/troubleshooting.md`
- This report.

## Checks and results

- Selected backend navigation and resolver tests: `11 passed` (including the
  added unknown-catalog-identity guard in the final full run).
- Selected frontend player, overlay, details-page, and API tests: `40 passed`.
- Fresh backend image and full Pytest suite: `117 passed`.
- Ruff over backend application, migrations, and tests: passed.
- Full frontend Vitest suite: `64 passed` across 12 files.
- Strict Vue TypeScript check and Vite production build: passed.
- Docker Compose configuration validation: passed.
- Disposable SQLite migration upgraded through `0006_episode_matcher`; Alembic
  check reported `No new upgrade operations detected`.

## Known limitations

- Prefetch requires an already confirmed mapping for the next episode in the
  active torrent task. It intentionally does not search or activate another
  release in the background.
- Autoplay is a browser-local preference because multiple server-side user
  preference profiles are not implemented yet. Watch history remains scoped
  by the backend `profile_key`.
- Combined multi-episode files remain playable as one physical video, but an
  exact transition inside them needs future stored time boundaries.
- Real Prowlarr/qBittorrent playback and browser E2E on Debian remain required
  before removing the legacy source panel.

## Readiness for the next substage

D1 is complete and locally verified. No deployment was part of this substage.
