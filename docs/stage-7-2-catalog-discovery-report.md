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

## Changed files

- Backend catalogue API, service, configuration, dependency wiring, and the
  new `services/metadata/kinopoisk.py` adapter.
- Frontend router, navigation, API types/client, and `DiscoveryPage.vue`.
- Compose/example environment configuration, tests, and catalogue/deployment
  documentation.

## Checks and test results

- Backend Pytest in the pinned Python 3.12 test image: 146 passed.
- Backend Ruff: passed.
- Frontend Vitest in the pinned Node 24 image: 83 passed across 14 files.
- Frontend production build (`vue-tsc -b` and Vite): passed.
- Docker Compose configuration validation: passed.
- `git diff --check`: passed.
- `docker compose ps` and the API/frontend log query returned no entries, so no
  local KADR services were running and live provider acceptance was unavailable.

## Known issues

- Age filtering depends on Russian certifications present in TMDB; titles with
  no certification are omitted when an age is selected.
- TMDB does not expose the same Russian certification filter for TV discovery,
  so cartoon series are shown without an invented age classification.
- Kinopoisk Unofficial is optional, requires its own key, and has an external
  daily quota. It enriches search aliases but does not replace TMDB identities.

## Next actions

1. Configure the optional key on the isolated KADR deployment.
2. Verify representative Russian film/series queries against live providers.
3. Review age-filter coverage and decide whether a persisted certification
   enrichment cache is warranted in a later numbered increment.
