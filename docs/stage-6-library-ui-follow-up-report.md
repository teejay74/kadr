# Stage 6 follow-up — Library controls

## Completed work

- Restored «Сохранить в библиотеку» below the current web player for a film or
  episode played from a torrent. The action becomes available when that video
  file finishes downloading, even while other files in the torrent are incomplete.
- Added an optional file ID to library save requests. The API rejects a new save
  if the torrent now points to a different file.
- Added separate Android TV tabs for «Продолжить просмотр», «Моя библиотека»,
  and «Избранное», each accessible from the home screen and through D-pad navigation.

## Changed files

- Web: `frontend/src/components/LibrarySaveAction.vue`, `frontend/src/pages/MediaDetailsPage.vue`,
  `frontend/src/pages/MediaDetailsPage.test.ts`, and `frontend/src/services/api.ts`.
- API: `backend/app/schemas/library.py`, `backend/app/services/library/manager.py`,
  and `backend/tests/test_library.py`.
- Android TV: `MainViewModel.kt` and `ui/KadrTvApp.kt` under `android-tv/app/src/main/java/ru/kadr/tv/`.
- Documentation: `README.md`, `docs/api.md`, and `docs/android-tv.md`.

## Checks and results

- Backend: 160 Pytest tests passed, including rejection of a stale file selection.
  Ruff passed. The isolated API returned HTTP 200 from `/api/v1/system/health`
  with `database: ok`, and its startup and shutdown logs were normal.
- Web: 101 Vitest tests passed. Type checking and the production build passed.
  Tests cover saving through the current player and enabling the action when the selected file reaches 100%.
- Android TV: 25 unit tests passed and `assembleDebug` produced an APK. On a Google TV
  emulator, the D-pad opened the tabs from the home screen, switched among all
  three lists with server data, and moved focus down to a list item.

## Known issues and next actions

The web flow was checked locally with tests. The deployed web and API services
and a physical TV were outside this verification. Deploy the web and API
together so the server can validate the file ID sent by the new button.

## Android TV card layout follow-up

- `ui/KadrTvApp.kt` now uses compact poster grids for saved videos and
  favorites. It shares the poster component with the home screen. The tab
  labels stay readable when focus moves into the grid.
- Episode and resume cards use the same clipped horizontal layout. Images
  fill the left side to the rounded edge. Episode cards display the synopsis
  and separate play and watched actions. Resume cards keep the episode,
  position, and progress and use a narrower layout.
- `docs/android-tv.md` describes the new layouts and remote navigation.
- Gradle built the APK and all 28 Android unit tests passed. Google TV
  emulator checks covered the grids, resume cards, episode play and watched
  focus targets, and returning to Favorites after opening a series. The app
  loaded data from KADR and produced no Android runtime errors during the
  check. Install the APK on a physical TV to check the layout at its display
  scale.
