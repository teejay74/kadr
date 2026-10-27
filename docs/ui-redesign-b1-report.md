# UI redesign report — substage B1

Date: 2026-10-27

## Completed work

- Added a normalized, cached season-details endpoint at
  `GET /api/v1/series/{id}/seasons/{season_number}`.
- Added typed season and episode schemas without coupling catalogue identity to
  torrent tasks or physical files.
- Added shared `MediaHero`, `MediaActions`, `PlayButton`, `CastCarousel`,
  `PlaybackProgress`, and `MediaStatus` components.
- Added `SeasonSelector`, `EpisodeList`, and `EpisodeCard` with loading, empty,
  error, retry, focus, desktop, and mobile states.
- Moved the series episode list directly below the shared hero.
- Remembered the last selected season per series in browser-local storage.
- Retained the complete legacy `SourcesPanel` and current playback path. An
  episode click scrolls to that workflow and explicitly states that the file
  still needs confirmation until the new resolver is available.
- Added backend, API-client, component, and page integration tests.

## Changed files

Backend:

- `backend/app/api/v1/catalog.py`
- `backend/app/schemas/media.py`
- `backend/app/services/metadata/catalog.py`
- `backend/tests/test_catalog.py`

Frontend:

- `frontend/src/components/CastCarousel.vue`
- `frontend/src/components/EpisodeCard.vue`
- `frontend/src/components/EpisodeList.vue`
- `frontend/src/components/MediaActions.vue`
- `frontend/src/components/MediaHero.vue`
- `frontend/src/components/MediaStatus.vue`
- `frontend/src/components/PlaybackProgress.vue`
- `frontend/src/components/PlayButton.vue`
- `frontend/src/components/SeasonSelector.vue`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/services/api.ts`
- `frontend/src/styles/main.css`
- `frontend/src/types/media.ts`
- New and updated frontend tests for the API, episode list, season selector,
  and details-page season restoration.

Documentation:

- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/troubleshooting.md`
- This report.

## Checks and results

- Fresh backend test image: `80 passed` with Pytest.
- Fresh frontend test image: `40 passed` across 9 Vitest files.
- Vue strict TypeScript and production Vite build: passed during the fresh
  frontend image build.
- Ruff: passed with `--no-cache` in the read-only test container.
- Alembic upgraded a disposable test database through migration `0004` before
  backend tests. B1 adds no database migration and does not modify user data.
- Docker Compose configuration: validated separately after implementation.
- The application stack was not started, so no live health or service-log claim
  is made for this substage.

## Known limitations

- Episode cards do not yet resolve or launch a physical file. The legacy source
  panel remains the verified playback workflow.
- Episode progress/status components are structural in B1; current history is
  still title-level and cannot populate independent episode state.
- One torrent task still has one legacy `selected_file_id`; multiple episode
  bindings belong to B2.
- Library and watch-history uniqueness are still media-level. SQLite nullable
  uniqueness and preservation of legacy rows must be addressed and tested in
  B2 before episode-aware persistence is enabled.
- Metadata does not yet provide a backend-resolved next-episode transition.
- Next-episode prebuffering is deferred until the resolver and multi-file task
  bindings exist. It must remain bounded to one next episode and must not turn
  into automatic whole-season downloading.
- Profile-aware history cannot be added before a profile/user identity exists;
  B2 must include a nullable/default profile key that can evolve without data
  loss.

## Readiness for B2

B1 is complete and tested. The UI and API now have stable episode catalogue
identity that is independent of files. B2 can design the SQLite migration for
episode identity, file variants, multi-file torrent bindings, profile-aware
history, and legacy-row preservation. No B2 implementation has started.
