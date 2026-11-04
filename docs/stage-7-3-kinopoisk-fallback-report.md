# Stage 7.3 report — Kinopoisk metadata fallback

Date: 2026-11-04

## Completed work

- Replaced alias-only enrichment with a bounded Kinopoisk Unofficial metadata
  fallback for titles absent from TMDB.
- Added normalized Kinopoisk cards, details, posters, ratings, series seasons,
  and episodes while keeping credentials server-side.
- Rejected unrelated fuzzy provider results and retained canonical TMDB items
  whenever an exact TMDB title match exists.
- Added a reserved positive KADR ID namespace so Kinopoisk identities work in
  existing web, Android TV, source-search, library, and episode flows without
  colliding with TMDB IDs.
- Added persistent caching and stale-on-outage behavior for Kinopoisk payloads.

## Changed files

- Backend Kinopoisk transport, catalogue orchestration, dependency wiring, and
  catalogue tests.
- README, API, architecture, deployment, and troubleshooting documentation.

## Checks and test results

- Targeted catalogue tests: 10 passed.
- Full backend Pytest: 148 passed.
- Backend Ruff: passed.
- Frontend Vitest: 82 passed across 14 files.
- Frontend production build (`vue-tsc -b` and Vite): passed.
- Docker Compose configuration and `git diff --check`: passed.
- Android TV source did not require a change: its existing `Int` catalogue ID
  path supports the reserved range. The previously verified client remains at
  19 passed tests with a successful debug build and lint. A repeat run on this
  workstation was unavailable because no Android SDK is currently installed;
  the existing verified APK was left unchanged.

## Known issues

- Kinopoisk Unofficial is an external service with its own availability and
  daily quota.
- Kinopoisk does not provide the same cast, trailer, episode-runtime, and still
  image coverage as TMDB; missing fields remain empty rather than fabricated.
- Provider-backed IDs are an internal KADR namespace and are not raw Kinopoisk
  IDs.

## Next actions

1. Run the complete regression suites and live acceptance for «Котёнок Котэ».
2. Deploy only the KADR API after the exact checkout passes all available checks.
3. Confirm Photodom remains untouched and healthy.
