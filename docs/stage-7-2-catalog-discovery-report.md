# Stage 7.2 report — catalogue discovery and Russian search

Date: 2026-11-04

## Completed work

- Added dedicated Новинки and Мультфильмы routes to the web navigation.
- Added bounded 365-day discovery excluding future releases; films require a
  regional TMDB digital release (type 4), not a theatrical-only premiere.
- Added Russian 0+/6+/12+/16+/18+ film certification filtering for animation.
- Added an optional Kinopoisk Unofficial alias adapter that improves Russian
  title search while preserving canonical TMDB identities.
- Kept the secondary provider key server-side and made its outage non-fatal.
- Added Новинки, Мультфильмы, and D-pad age filters to the Android TV client.

## Changed files

- Backend catalogue API, service, configuration, dependency wiring, and the
  new `services/metadata/kinopoisk.py` adapter.
- Frontend router, navigation, API types/client, and `DiscoveryPage.vue`.
- Android TV navigation, catalogue queries, age-filter controls, and tests.
- Compose/example environment configuration, tests, and catalogue/deployment
  documentation.

## Checks and test results

- Backend Pytest in the pinned Python 3.12 test image: 146 passed.
- Backend Ruff: passed.
- Frontend Vitest in the pinned Node 24 image: 83 passed across 14 files.
- Frontend production build (`vue-tsc -b` and Vite): passed.
- Docker Compose configuration validation: passed.
- `git diff --check`: passed.
- Android TV unit tests: 19 passed; debug build and lint passed.
- Server-side acceptance on the exact deployed checkout: backend 146 passed,
  Ruff passed, frontend 83 passed, and the production frontend build passed.
- Deployed commit `e7878ad3ad9ca450c021cf2d4dd6507ff785f9f6` to the isolated
  KADR Compose project on `192.168.1.69`; only `api` and `web` were rebuilt and
  recreated. Both containers and all existing KADR supporting services report
  healthy.
- API health reports `status=ok` and `database=ok`; Alembic is at
  `0007_playback_track_preferences (head)`.
- Live smoke requests for digital movie releases, animated films filtered to
  6+, and recent series each returned 20 catalogue items. Web routes `/new` and
  `/cartoons` both returned HTTP 200.
- Created the pre-deployment database backup
  `/srv/kadr/backups/kadr-pre-catalog-20261104-1825.db`; SQLite integrity check
  returned `ok` and its SHA-256 is
  `01d215f486f598096584e345c4c4d2c66f34134f9f71502841520fb2a57414d9`.
- The separate Photodom container remained healthy and was not modified or
  restarted.

## Known issues

- Age filtering depends on Russian certifications present in TMDB; titles with
  no certification are omitted when an age is selected.
- TMDB does not expose the same Russian certification filter for TV discovery,
  so cartoon series are shown without an invented age classification.
- Kinopoisk Unofficial is optional, requires its own key, and has an external
  daily quota. It enriches search aliases but does not replace TMDB identities.
- `KADR_KINOPOISK_API_KEY` is not configured on the current deployment, so the
  optional Russian-title alias enrichment remains disabled until a key is
  supplied. TMDB discovery and search continue to operate normally.

## Next actions

1. Configure the optional Kinopoisk Unofficial key on the isolated KADR
   deployment.
2. Verify representative Russian film/series queries against live providers.
3. Review age-filter coverage and decide whether a persisted certification
   enrichment cache is warranted in a later numbered increment.
