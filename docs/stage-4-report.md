# Stage 4 report — Torrent Manager

Date: 2026-10-24

## Completed work

- Added an isolated qBittorrent 5.3.0 service with a digest-pinned image,
  loopback-only Web UI, persistent KADR-only configuration/download mounts,
  health check, restart policy, memory limit, and private Compose network.
- Added a typed async qBittorrent Web API adapter with cookie authentication,
  add, list, file list/priority, start, stop, and status operations.
- Added persistent torrent-task identity linking a media item, opaque Prowlarr
  source, qBittorrent hash, selected file, and configured storage path.
- Added REST endpoints and UI actions for adding a source, inspecting files,
  choosing one supported video, starting, stopping, and refreshing real state.
- Added the `MetadataReceived` stop condition: magnet metadata can be fetched
  without proceeding into an unattended content download.
- Added maximum-active-torrent and free-space gates. The API can only inspect
  the KADR download mount read-only; qBittorrent owns writes.
- Added traversal/absolute-path rejection for torrent file selection. No
  deletion, streaming, playback, or transcoding behavior was introduced.

## Verification

- Backend Pytest: 19 tests passed.
- Backend Ruff lint: passed.
- Frontend Vitest: 4 files / 8 tests passed.
- Vue strict TypeScript check: passed.
- Frontend production build: passed.
- Docker Compose configuration: valid.
- Runtime health: API, web, Prowlarr, and qBittorrent reported healthy.
- Live Prowlarr/KADR check: the free Blender film Sintel was found through the
  configured indexer and added through the KADR REST API with HTTP 201.
- Live adapter acceptance: qBittorrent 5.3.0 received official Sintel metadata,
  listed 11 files, selected an MP4, entered `downloading`, transferred 534,204
  bytes, and returned to `stoppedDL` after the stop command.

The live test used the free Creative Commons Sintel fixture documented by the
WebTorrent project. It was stopped after a few seconds; the partial test data
and test task were not deleted because destructive cache lifecycle is outside
Stage 4.

## Created files

- `backend/app/api/v1/torrents.py`
- `backend/app/models/torrent_task.py`
- `backend/app/repositories/torrent_tasks.py`
- `backend/app/schemas/torrents.py`
- `backend/app/services/torrents/exceptions.py`
- `backend/app/services/torrents/manager.py`
- `backend/app/services/torrents/qbittorrent.py`
- `backend/migrations/versions/0003_torrent_tasks.py`
- `backend/tests/test_torrents.py`
- `data/downloads/.gitkeep`
- `data/qbittorrent/.gitkeep`
- `docs/qbittorrent.md`
- `docs/stage-4-report.md`

## Updated files

- `.env.example`, `.gitignore`, `README.md`, `docker-compose.yml`
- backend dependency wiring, router, configuration, application error mapping,
  model exports, and server-side source resolution
- frontend source panel, API service, media types, styles, and their tests
- API, architecture, deployment, storage, streaming, and troubleshooting docs

## Known limits and next actions

- A magnet with no reachable metadata source legitimately has no selectable
  files; KADR exposes the real state and does not synthesize data.
- The development Compose file does not publish qBittorrent's peer-listen port.
  Production connectivity must be decided only after the required Debian host
  and network audit.
- Stage 5 may add HTTP Range streaming only after its dedicated safety and
  behavior test matrix is implemented. Automatic transcoding remains forbidden.
- Stage 6 must own safe cache cleanup; Stage 4 intentionally has no delete API.

No Photodom path, service, disk, mount, firewall, or Debian host was accessed or
changed.
