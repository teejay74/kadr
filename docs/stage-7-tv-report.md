# Stage 7.1 report — Android TV web controls

Date: 2026-10-28

## Completed work

- Added automatic Android TV / Google TV-style mode detection with explicit
  `?tv=1` and `?tv=0` test overrides.
- Added geometric D-pad navigation across visible links, buttons, form controls,
  and disclosure controls. Focus follows the closest visual row or column and
  scrolls into view.
- Added OK/Select activation and Back handling. Back first closes the active
  source selector, episode matcher, next-episode overlay, or player, then falls
  back to router history/home.
- Added larger TV targets, cards, high-contrast focus treatment, and a compact
  TV-mode indicator without changing the normal desktop/mobile layout.
- Added focused-player remote controls: left/right seek ten seconds, up/down
  change volume, OK toggles playback, and Back closes the player.
- Added unit coverage for spatial focus selection and player remote keys.

## Changed files

- `frontend/src/composables/useTvNavigation.ts` and its test.
- `frontend/src/layouts/AppShell.vue`.
- `frontend/src/components/KadrPlayer.vue` and its test.
- TV Back hooks in `SourceSelector.vue`, `EpisodeMatchDialog.vue`, and
  `NextEpisodeOverlay.vue`.
- `frontend/src/styles/main.css`, `README.md`, and `docs/architecture.md`.

## Checks and test results

- Production frontend build (`vue-tsc -b` and Vite): passed in the pinned Node
  build container.
- Frontend Vitest: 79 passed across 14 files.
- Docker Compose configuration validation: passed.
- `git diff --check`: passed.
- `docker compose ps` returned no running KADR containers, so live health and
  service logs were unavailable and no deployment was attempted.

## Known issues

- This is a TV-adapted web client, not the future native Media3 ExoPlayer APK.
- Physical-device acceptance is still required; desktop emulation cannot prove
  key codes, fullscreen behavior, codec support, audio-track switching, or
  subtitle rendering on a particular television.
- Search is hidden in TV mode until an on-screen-keyboard interaction is
  designed and verified for the target remote.
- Samsung Tizen and LG webOS remain unverified and are not claimed supported.

## Next actions

1. Deploy this build to the isolated KADR web service without exposing internal
   services.
2. Run the Stage 7 compatibility checklist on the target Android TV / Google TV:
   D-pad, OK, Back, focus visibility, fullscreen, seek, resume, H.264/AAC Direct
   Play, compatible playback, subtitles, and audio selection.
3. Record the device model, Android/Google TV version, browser or WebView build,
   tested containers/codecs, and failures before declaring Stage 7 complete.
