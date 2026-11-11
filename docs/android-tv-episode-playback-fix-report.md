# Android TV 0.7.3 episode playback fix

Date: 2026-11-11

## Completed work

- D-pad Up and Down target adjacent episode rows and scroll the lazy list when
  the target is off-screen. Navigation stays in the current button column.
  Up from the first episode returns to the selected season.
- Manual selection and automatic continuation show the episode preparation
  screen immediately. The download percentage, initial buffer and available
  speed come from the playback resolver and stream readiness API.
- Media3 buffering remains visible with the controls hidden. Playback failures
  display a message, and episode preparation failures appear above the list.
- The debug APK uses version `0.7.3` and version code `14`.

## Changed files

- `android-tv/app/build.gradle.kts`
- `android-tv/app/src/main/java/ru/kadr/tv/MainViewModel.kt`
- `android-tv/app/src/main/java/ru/kadr/tv/data/KadrApi.kt`
- `android-tv/app/src/main/java/ru/kadr/tv/data/Models.kt`
- `android-tv/app/src/main/java/ru/kadr/tv/ui/KadrTvApp.kt`
- `android-tv/app/src/main/java/ru/kadr/tv/ui/PlayerScreen.kt`
- `README.md`, `docs/android-tv.md`

## Checks and test results

- `./gradlew --offline testDebugUnitTest assembleDebug` passed. All 23 JVM
  tests passed, and the generated APK metadata reports version `0.7.3`.
- The Google TV emulator and a local API test fixture verified scrolling in both
  directions through a 14-episode season, including navigation in the watched
  button column and the return to the season selector.
- The emulator showed download progress for manual selection and automatic
  continuation within a season and across a season boundary. Back returned to
  the list, and Media3 opened when the fixture reported readiness.
- A stalled stream kept the buffering message visible with the controls
  hidden. An HTTP stream failure displayed a player error.
- Local Docker inspection found no running KADR Compose containers to check.
- `git diff --check` passed.

## Known issues and next actions

- Verification used a Google TV emulator and an isolated HTTP fixture. Install
  the APK on the target TV and repeat the checks using the live KADR server.
