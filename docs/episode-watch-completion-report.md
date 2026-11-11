# Episode watch completion

Date: 2026-11-11

## Completed work

- Web and Android TV report the video intervals actually played. The shared
  history merges those intervals by episode and profile. It marks the episode
  watched when their combined length exceeds 80% of the video duration.
- Seeking skips the intervening interval. Replaying a portion counts it once.
  Manual removal of the watched mark clears the accumulated intervals.
- Both clients display the status returned by the history API. Existing
  history and movie completion continue to use their existing fields and rules.
- Android TV builds as version `0.8.0` with version code `15`.

## Changed files

- Backend history schema, service, repository and model in
  `backend/app/`, plus Alembic revision `0008_episode_played_ranges`.
- Web player, series and library pages, API client and related Vitest cases in
  `frontend/src/`.
- Android TV Media3 player, played-range tracker, history client, view model,
  APK version and tracker tests in `android-tv/`.
- `README.md`, `docs/android-tv.md` and `docs/api.md`.

## Checks and test results

- Pytest passed all 155 tests. The history API regression test covers a seek,
  overlapping ranges, simultaneous reports, exactly 80%, crossing the
  threshold, and clearing the mark. Alembic upgraded a test database to
  `0008_episode_played_ranges`.
- The production web build and all 95 Vitest tests passed.
- `./gradlew --offline testDebugUnitTest assembleDebug` built Android TV 0.8.0.
  All 25 JVM tests passed. The tracker tests cover skipping, pause, resume and
  overlapping playback.
- On the Google TV emulator with an isolated KADR API, a seek near the end
  preserved the unwatched state. Continuous playback passed the threshold
  before the episode ended and showed the watched mark in the episode list.
  The API health endpoint reported `ok`, and the logs showed successful
  history writes.
- Ruff passed for the changed Python files. `git diff --check` passed.

## Known issues and next actions

- Existing incomplete history provides a resume position. Coverage starts
  with the first report that contains played ranges.
- Apply migration `0008_episode_played_ranges` when deploying the updated API,
  publish the matching web build, and install Android TV 0.8.0 on the target
  TV. Verification used isolated test environments.
