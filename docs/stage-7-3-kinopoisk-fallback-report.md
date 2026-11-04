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
- Fixed the Episode Matcher follow-up found during live use: paths without an
  explicit `S01E02` or `Сезон` marker now load the regular seasons from the
  catalogue item and match against Kinopoisk episode titles. Provider-specific
  TMDB warnings were replaced with accurate catalogue-metadata wording.

## Changed files

- Backend Kinopoisk transport, catalogue orchestration, dependency wiring, and
  catalogue and Episode Matcher tests.
- Episode Matcher service and provider-neutral web confirmation dialog.
- README, API, architecture, deployment, and troubleshooting documentation.

## Checks and test results

- Targeted catalogue tests: 10 passed.
- Episode Matcher regression suite: 21 passed, including a Kinopoisk-backed
  `Котёнок Котэ/01.../002. Трактор.mp4` case.
- Full backend Pytest: 149 passed.
- Backend Ruff: passed.
- Frontend Vitest: 84 passed across 14 files.
- Frontend production build (`vue-tsc -b` and Vite): passed.
- Docker Compose configuration and `git diff --check`: passed.
- Production deployment preflight passed: the KADR checkout was clean, all
  KADR services were healthy, storage had sufficient free space, and Photodom
  was healthy before any mutation.
- A pre-deployment SQLite backup was created at
  `/srv/kadr/backups/kadr-pre-kinopoisk-fallback-20261104-210006.db`; SQLite
  integrity check returned `ok`, SHA-256:
  `86654054a2bfa7175e0339f1c115430526bff7b5b0a6b3d30b1a55b89203dba7`.
- The production runtime image built successfully and only the KADR API
  container was recreated. Health check returned `status=ok` and
  `database=ok`; Alembic remained at `0007_playback_track_preferences (head)`.
- Live search acceptance passed for both `Котёнок Котэ` and `Котенок Котэ`:
  both resolve to KADR ID `1501115558`, title `Котёнок Котэ` (2015). Details
  expose a poster, 5 seasons, and 279 episodes; season 1 exposes 150 episodes
  and begins with `Светофор`. A cached search completed in 0.096 seconds.
- Post-deployment checks passed: every KADR service and the separate Photodom
  container remained healthy; the production checkout was clean at commit
  `9919d5796ee843bb42e8b88e722cc7e8ad766022`.
- Follow-up Episode Matcher deployment completed at commit
  `3e5623d51f00804340a51109a894e9eef65d0fbd`. Before the update the affected
  live «Котёнок Котэ» task returned 270 files with
  `metadata_available=false` and zero episode options. After the update it
  returns `metadata_available=true` and options for all 270 files: 188
  probable matches and 82 ambiguous matches requiring explicit confirmation.
  The live examples resolve `Плохие птицы` to season 5 episode 1 and offer
  catalogue candidates for the ambiguous `Трактор` filename. Analysis
  completed in 5.026 seconds.
- The follow-up deployment rebuilt only the KADR API and web containers. Both
  are healthy, Alembic remains at `0007_playback_track_preferences (head)`,
  all supporting KADR services remain healthy, and Photodom remains healthy
  and untouched.
- The follow-up pre-deployment backup is
  `/srv/kadr/backups/kadr-pre-episode-matcher-20261104-212518.db`; integrity
  check returned `ok`, SHA-256:
  `76ab8691739983ea0b644c340e0615ea69fe1c8f3823402d29a50fc30b80f108`.
- A repeat server-side Pytest image build was cancelled after the production
  dependency layer completed because the external PyPI transfer stalled while
  downloading the dev-only Ruff wheel. This did not affect the runtime build;
  the full local backend suite and Ruff had already passed on the deployed
  commit.
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

1. Monitor Kinopoisk Unofficial quota and provider availability in normal use.
2. Re-run Android TV instrumentation on a workstation with an installed Android
   SDK when client-side code next changes.
