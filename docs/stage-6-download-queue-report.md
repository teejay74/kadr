# Stage 6 follow-up — Queue files from Downloads

## Completed work

- The web Downloads page can enable one skipped video or all remaining
  supported videos in a release with a selected playback file. It rereads
  the file priorities after the action and shows which videos are queued.
- KADR enables additional files at normal priority and uses the existing
  storage and active-task checks. The operation retains existing pieces and
  the selected playback file. Next-episode prefetch adds to the same queue.

## Changed files

- API and services: `backend/app/api/v1/torrents.py`,
  `backend/app/schemas/torrents.py`,
  `backend/app/services/torrents/manager.py`, and
  `backend/app/services/playback/navigation.py`.
- Web: `frontend/src/pages/DownloadsPage.vue` and
  `frontend/src/services/api.ts`.
- Tests: `backend/tests/test_torrents.py`,
  `backend/tests/test_episode_navigation.py`, and
  `frontend/src/pages/DownloadsPage.test.ts`.
- Documentation: `README.md`, `docs/api.md`, and `docs/architecture.md`.

## Checks and results

- 161 Pytest tests and 109 Vitest tests passed. Ruff, TypeScript checking,
  and the production web build passed.
- An isolated API returned HTTP 200 with `database: ok`. Its startup and
  shutdown logs were normal. The queue route returned the expected 404 for
  an unknown task. Tests cover the partially downloaded file, bulk add,
  repeated requests, invalid paths, and preserving the queue when switching
  episodes.

## Known issues and next actions

- Live qBittorrent downloads were outside the local verification. Deploy
  the API and web client together, then verify with an existing release.
