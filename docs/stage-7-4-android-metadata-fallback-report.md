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
- Production preflight, backup, deployment, and live acceptance: pending.

## Known issues

- The fallback depends on the separately configured Kinopoisk Unofficial
  service and its quota.
- It is deliberately unavailable when title/type/year do not match exactly;
  KADR returns the original provider error instead of opening another work.
- Restoring correct TMDB DNS and HTTPS connectivity remains desirable because
  Kinopoisk field coverage differs from TMDB.

## Next actions

1. Complete full automated checks and build the `0.7.1` APK.
2. Audit and back up the production host, deploy only changed KADR services,
   and verify the live Android detail-to-season flow.
3. Install the APK on the television through an authorized ADB connection or
   the documented USB workflow.
