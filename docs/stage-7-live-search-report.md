# Stage 7 follow-up — Live catalogue search

## Completed work

- The web search field shows a dropdown after two characters. The mixed film
  and series list highlights matches and shows original titles and release
  years when available. Arrow keys and Enter select a result, and Escape
  closes the list. Enter also opens the full results page when no suggestion
  is selected.
- Android TV shows the same information in a scrollable list under the search
  field. With the on-screen keyboard closed, Down moves from the field to the
  first suggestion and OK opens the selected title.
- Both clients debounce input and reuse the existing catalogue search API.

## Changed files

- Web: `GlobalSearch.vue`, `GlobalSearch.test.ts`, `AppShell.vue`,
  `services/api.ts`, and `styles/main.css` under `frontend/src/`.
- Android TV: `MainViewModel.kt`, `data/KadrApi.kt`, `data/Models.kt`,
  and `ui/KadrTvApp.kt` under `android-tv/app/src/main/java/ru/kadr/tv/`,
  plus `AndroidManifest.xml`.
- Documentation: `README.md`, `docs/android-tv.md`, and
  `docs/architecture.md`.

## Checks and results

- All 108 Vitest tests passed. Type checking and the production web build
  passed. Tests cover delayed queries, stale responses, highlighting,
  keyboard selection, and navigation to full results.
- All 28 Android unit tests passed and `assembleDebug` produced an APK.
  On a Google TV emulator, real catalogue results appeared for `Alien`.
  Down selected «Чужой / Alien (1979)» and OK opened the film details.
- The deployed API returned healthy SQLite status and both catalogue search
  endpoints returned HTTP 200 for `чуж`. The emulator application logs
  showed no runtime errors during the search check.

## Known issues and next actions

- The updated web client is built locally. The Android APK was checked on
  an emulator. Deploy the web update and install the APK on a physical TV
  for device acceptance.
