# Stage 7.4 report — Android TV metadata outage fallback

Date: 2026-11-05

## Completed work

- Diagnosed the Android TV failure before playback: the device opened a saved
  series card, but its TMDB detail request returned a controlled `502`, so no
  playback-resolution request was made.
- Added a bounded detail fallback that uses a trusted card title, media type,
  and year to resolve an exact Kinopoisk object while TMDB is unreachable.
- Made Android TV adopt the returned reserved KADR identity before loading a
  season or searching for a source.
- Added a prominent, dismissible error panel to catalogue, discovery, search,
  and library screens so failures cannot remain below a long list.
- Bumped the native Android TV client to `0.7.1` (`versionCode` 12).

## Changed files

- Backend catalogue routes, metadata orchestration, and catalogue tests.
- Android TV API paths, view-model detail flow, error presentation, version,
  and unit tests.
- README, API, architecture, Android TV, and troubleshooting documentation.

## Checks and test results

- Targeted backend catalogue suite: 12 passed.
- Full backend Pytest: 151 passed.
- Backend Ruff: passed.
- Android TV: 20 unit tests passed; lint and debug APK build passed. APK
  SHA-256: `512294b346cf5bdb1c1338dd25d10ad0024cf1678f05abfaf67886f0b7cb7789`.
- Docker Compose configuration and `git diff --check`: passed.
- Production preflight passed: the KADR checkout was clean, all KADR services
  and the separate Photodom container were healthy, 106 GiB of disk and
  6.7 GiB of memory were available, and the database/network mounts remained
  isolated.
- Created `/srv/kadr/backups/kadr-pre-android-tmdb-fallback-20261105-114100.db`;
  integrity check returned `ok`, SHA-256:
  `1ab22e95c499a5283a7f03fc4e7d7f66d8b9a552e1362a76bb0af909ac3a6d36`.
- Deployed commit `b04eedb6f0c84cbd9dab2c507bd119c7ae39373b` by rebuilding and
  recreating only the KADR API container. It became healthy; the health endpoint
  returned `database=ok`, and Alembic remained at
  `0007_playback_track_preferences (head)`.
- Live Android detail flow for TMDB series `1399` returned `Игра Престолов`
  (2011), nine seasons, and season 1 with ten episodes beginning with
  `Зима близко`. TMDB DNS/HTTPS had recovered by acceptance time, so the live
  request used TMDB; the forced-outage Kinopoisk branch is covered by backend
  tests, including rejection of a mismatched year.
- Post-deployment checks passed: all KADR services and Photodom remained healthy
  and the production checkout was clean.
- Network ADB installation was not possible because the television at the last
  observed address refused TCP port 5555. The verified APK remains ready for
  installation after wireless debugging is enabled or by the documented USB
  workflow.

## Known issues

- The fallback depends on the separately configured Kinopoisk Unofficial
  service and its quota.
- It is deliberately unavailable when title/type/year do not match exactly;
  KADR returns the original provider error instead of opening another work.
- Restoring correct TMDB DNS and HTTPS connectivity remains desirable because
  Kinopoisk field coverage differs from TMDB.

## Next actions

1. Install the `0.7.1` APK on the television after enabling an authorized ADB
   connection, or use the documented USB workflow.
2. Monitor metadata-provider availability and confirm the fallback on the
   physical TV if TMDB becomes unreachable again.
