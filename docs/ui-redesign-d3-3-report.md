# Audio and subtitle tracks D3.3 report

## Completed work

- Added an “Аудио и субтитры” menu to the shared KadrPlayer used by films,
  episodes, and saved library items.
- Added strict TypeScript API models and client methods for track discovery and
  preference writes on torrent and library sources.
- Displayed language, optional title/studio, codec, channels, default, and
  forced flags without requiring a track title.
- Applied audio and subtitle selections through native browser track APIs only
  when those APIs exist and a language/title match is safe.
- Preserved the current media URL and playback position during native switching.
- Persisted selections when a browser cannot switch an MKV track and showed an
  explicit saved-but-not-applied message.
- Kept subtitle-off explicit and disabled unsupported subtitle entries.
- Passed library item identity into KadrPlayer so saved files use the library
  track endpoints rather than torrent endpoints.
- Kept FFmpeg fully explicit; opening the menu or selecting a preference never
  starts conversion.

## Changed files

- `frontend/src/components/KadrPlayer.vue`
- `frontend/src/components/KadrPlayer.test.ts`
- `frontend/src/pages/LibraryPage.vue`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/services/api.ts`
- `frontend/src/services/api.test.ts`
- `frontend/src/styles/main.css`
- `frontend/src/types/media.ts`
- `README.md`
- `docs/streaming.md`
- `docs/troubleshooting.md`
- This report.

## Checks and test results

- Focused KadrPlayer/API Vitest set: `34 passed`.
- Full frontend Vitest suite: `70 passed` across 13 files.
- Strict Vue TypeScript and Vite production build: passed.

## Known limitations

- Browser-native alternate audio support is not portable, especially for MKV.
- D3.3 saves but cannot apply a non-native audio track until an explicit
  selected-track compatible stream exists.
- Embedded text subtitles depend on the browser exposing a matching TextTrack;
  WebVTT extraction and bitmap subtitle burn-in are not implemented here.
- No FFmpeg process starts from this menu in D3.3.

## Completion and next actions

- D3.3 is complete and locally verified.
- D3.4 should create an explicit compatible stream for the selected audio track,
  preferring video stream copy, and restore position after changing the URL.
- Text subtitle WebVTT extraction should remain separate from bitmap burn-in so
  ordinary Direct Play stays untouched.

