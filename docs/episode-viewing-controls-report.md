# Episode viewing controls report

Date: 2026-11-06

## Completed work

- Fixed bidirectional up/down focus movement inside the series episode list for
  keyboard and Android TV remote users. At the list boundaries, focus can still
  leave the list through the existing page-level navigator.
- Loaded the default profile's persisted episode history on the series details
  page and exposed partial/completed state and playback progress per episode.
- Added an explicit per-episode action to add or remove the watched mark through
  the existing versioned history API.
- Reflected a completed episode immediately after playback ends.
- Enabled the existing five-second automatic next-episode countdown by default;
  a viewer's disabled preference remains persisted in browser storage.
- Changed the fresh Android TV connection-form default to
  `http://192.168.1.69` without changing saved server addresses.
- Bumped the Android TV application to `0.7.2` (`versionCode` 13) so the APK can
  be installed over version `0.7.1` as an update.
- Fixed the native Android TV focus override that sent every episode's Up key
  directly to the season row; only the first episode now has that override.
- Added native watched-state display/toggling backed by the shared history API.
- Added native Media3 completion continuation to the next numbered episode or
  the first episode of the nearest following season. A player session key
  forces Media3 recreation even when two episodes resolve to the same stream
  route.

## Changed files

- `frontend/src/components/EpisodeCard.vue`
- `frontend/src/components/EpisodeList.vue`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/services/api.ts`
- `frontend/src/styles/main.css`
- Related frontend Vitest files
- `android-tv/app/src/main/java/ru/kadr/tv/data/ServerAddress.kt`
- `android-tv/app/src/main/java/ru/kadr/tv/data/Models.kt`
- `android-tv/app/src/main/java/ru/kadr/tv/MainViewModel.kt`
- `android-tv/app/src/main/java/ru/kadr/tv/ui/KadrTvApp.kt`
- `android-tv/app/src/main/java/ru/kadr/tv/ui/PlayerScreen.kt`
- Related Android JVM unit tests
- `android-tv/app/src/test/java/ru/kadr/tv/data/ServerAddressTest.kt`
- `README.md`, `docs/architecture.md`, and `docs/android-tv.md`

## Checks and test results

- `docker compose --profile test build web-test`: passed, including strict
  TypeScript checking and the Vite production build.
- `docker compose --profile test run --rm web-test`: 14 files and 88 tests
  passed.
- `git diff --check`: passed.
- `./gradlew testDebugUnitTest`: not executed because this workstation has no
  Java runtime. Focused JVM tests cover the default URL and next episode/season
  selection and are ready for an Android build environment.
- Read-only Docker inspection showed no running KADR services, so there were no
  KADR health endpoints or service logs to inspect. Unrelated running projects
  were not modified.

## Known issues

- Android unit and APK builds still require a JDK/Android build environment.
- Automatic continuation still needs a resolvable next episode. When no exact
  persisted file binding exists, the existing source-selection flow is shown.

## Next actions

1. Run `./gradlew testDebugUnitTest` and `./gradlew assembleDebug` in the Android
   build environment.
2. Verify D-pad focus, watched toggling, and the end-of-episode countdown on the
   target television.
