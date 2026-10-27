# UI redesign report — substage C1

Date: 2026-10-27

## Completed work

- Added one backend playback resolver for films and logical series episodes.
- Made source priority explicit: available saved-library copy first, then a
  persisted torrent file variant. Episode resolution never guesses from a file
  name.
- Reused the legacy selected film file while `selected_file_id` remains in the
  compatibility period.
- Returned controlled `ready`, `buffering`, `source_required`, and
  `unavailable` states with safe stream identifiers, buffer/download state, and
  profile/episode-aware resume position.
- Kept concrete torrent-file selection and piece readiness decisions in the
  backend.
- Wired both the film hero action and series episode cards to the same resolver
  and shared player.
- Allowed the player to activate from a resolved source and consume the
  resolver's resume position.
- Bounded automatic readiness polling to twelve five-second checks and exposed
  retry after a stalled buffer instead of leaving an infinite loading state.
- Retained the legacy `SourcesPanel` as the manual fallback for missing or
  unavailable sources.

## Changed files

Backend:

- `backend/app/api/dependencies.py`
- `backend/app/api/v1/playback.py`
- `backend/app/repositories/episodes.py`
- `backend/app/schemas/playback.py`
- `backend/app/services/library/manager.py`
- `backend/app/services/playback/resolver.py`
- `backend/tests/test_playback_resolver.py`

Frontend:

- `frontend/src/components/KadrPlayer.vue`
- `frontend/src/components/KadrPlayer.test.ts`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/pages/MediaDetailsPage.test.ts`
- `frontend/src/services/api.ts`
- `frontend/src/services/api.test.ts`
- `frontend/src/types/media.ts`

Documentation:

- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/troubleshooting.md`
- This report.

## Checks and results

- Fresh backend test image and full Pytest suite: `90 passed`.
- The backend suite upgraded its disposable SQLite database through migration
  `0005` before running.
- Ruff over the backend application, migrations, and tests: passed.
- Fresh frontend image, strict Vue TypeScript check, and Vite production build:
  passed.
- Full frontend Vitest suite: `49 passed` across 9 files.
- Dedicated tests cover library priority and resume, persisted episode variant
  reuse, buffering, missing/unavailable sources, the API contract, movie and
  episode UI actions, and automatic player activation.
- No schema change was required in C1; `alembic check` reported no new upgrade
  operations and Docker Compose configuration validation passed.
- The production stack and Debian host were not changed, so this report makes
  no live service-health or production-playback claim.

## Known limitations

- C1 does not implement the replacement modal `SourceSelector`; missing or
  unavailable sources intentionally fall back to the retained `SourcesPanel`.
- Backend-owned next-episode and cross-season resolution are not part of C1.
  The frontend still does not calculate a next episode by incrementing a number.
- Automatic near-end buffering of exactly one backend-resolved next episode is
  deferred with next-episode resolution. No automatic season-wide download was
  added.
- The resolver tries persisted variants in recency order, but C1 has no user
  quality/variant chooser.
- Film compatibility still uses `selected_file_id` until the migration away
  from that legacy field is complete.
- Full browser E2E playback against qBittorrent, saved library files, and the
  Debian host remains an acceptance check after a separately approved deploy.

## Readiness for the next substage

C1 is complete and locally verified. C2 can replace the missing/unavailable
fallback with the specified source-selection modal while keeping
`SourcesPanel` in place for regression comparison. C2 must add new tests and
must not remove the legacy panel until film, series, and library playback pass
end-to-end checks.
