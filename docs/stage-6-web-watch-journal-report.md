# Stage 6 follow-up — Web watch journal

## Completed work

- Added **Продолжить просмотр** to the web navigation. It opens the
  default-profile journal shared with Android TV, with the newest updates
  first and filters for in-progress and completed items.
- Film and episode rows display their saved position, runtime when known,
  and last update. **Продолжить** opens the exact film or episode and seeks
  to the latest position returned by the resolver. When the source needs
  replacement, the existing source selector opens.
- Legacy series records with a saved position and no episode identity link
  to episode selection.

## Changed files

- Journal and navigation: `WatchHistoryPage.vue`, `AppShell.vue`,
  `router/index.ts`, and `styles/main.css` under `frontend/src/`.
- Playback: `MediaDetailsPage.vue`, `KadrPlayer.vue`, and
  `utils/formatPlaybackTime.ts` under `frontend/src/`.
- Tests: `WatchHistoryPage.test.ts`, `MediaDetailsPage.test.ts`, and
  `KadrPlayer.test.ts`.
- Documentation: `README.md`, `docs/architecture.md`, and `docs/api.md`.

## Checks and results

- All 106 Vitest tests and 160 Pytest tests passed. Type checking, the
  production web build, Ruff, and `git diff --check` passed.
- On an isolated SQLite database, migrations reached the current head.
  The API reported HTTP 200 and `database: ok`. A newly saved episode
  appeared in the journal endpoint and the resolver returned its 125-second
  position. Startup and shutdown logs were normal.

## Known issues and next actions

- Verification used local tests and the isolated API. Check the layout and
  resume playback with a real video on the deployed web service after
  deployment is authorized.
