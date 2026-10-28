# UI redesign D2.1 report

## Completed work

- Extended stream readiness with the selected file's progress, current download
  state, and speed instead of reusing aggregate torrent progress in the player.
- Updated the Playback Resolver and KadrPlayer to use that selected-file state.
- Allowed MKV, WebM, MPEG transport streams, and other start-readable containers
  to become ready from their initial pieces without waiting for file-tail data.
- Retained the bounded tail probe for MP4/MOV/M4V and AVI containers that may
  depend on trailing metadata or indexes.
- Kept every later HTTP Range read protected by its real qBittorrent piece
  availability; sparse files are still never treated as downloaded data.
- Verified that the current KadrPlayer contains one readiness invocation per
  activation. No duplicate invocation was present and no unnecessary change was
  made there.
- Kept Direct Play, compatible FFmpeg artifacts, Episode Matcher, prefetch,
  library data, and existing SQLite schema unchanged.

## Changed files

Backend:

- `backend/app/schemas/torrents.py`
- `backend/app/services/playback/resolver.py`
- `backend/app/services/streaming/manager.py`
- `backend/tests/test_playback_resolver.py`
- `backend/tests/test_streaming.py`

Frontend:

- `frontend/src/components/KadrPlayer.vue`
- `frontend/src/components/KadrPlayer.test.ts`
- `frontend/src/types/media.ts`

Documentation:

- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/streaming.md`
- `docs/troubleshooting.md`
- This report.

## Checks and test results

- Focused backend Streaming Manager and Playback Resolver tests: `26 passed`.
- Focused KadrPlayer and media-details tests: `20 passed`.
- Full backend Pytest suite: `119 passed`.
- Ruff over backend application, migrations, and tests: passed.
- Full frontend Vitest suite: `67 passed` across 13 files.
- Strict Vue TypeScript and Vite production build: passed.
- Fresh disposable SQLite migration chain through `0006_episode_matcher`: passed.
- Docker Compose configuration and `git diff --check`: passed.

## Known limitations

- A source can still stall if peers do not provide the required initial pieces.
- MP4/MOV/M4V and AVI intentionally keep a tail probe; their startup can remain
  slower when trailing metadata is unavailable.
- The readiness response reports selected-file progress only while the player is
  polling. The Downloads page continues to own ongoing background task status.
- Browser container and codec support is unchanged. Explicit compatible playback
  remains available and never starts automatically.

## Completion and next actions

- D2.1 is complete and locally verified.
- Deploy and repeat a live partial-MKV playback check on Debian when authorized.
- Start D3.1 Track Discovery API only after accepting this substage.
