# Deployment report — 2026-10-26

## Completed work

- Audited the Debian host before making changes.
- Deployed KADR to the new, separately owned `/srv/kadr` directory.
- Kept the Compose project, network, database, configuration, and data
  directories separate from Photodom.
- Published only the KADR nginx entry point on host port 80.
- Kept Prowlarr on `127.0.0.1:9696` and qBittorrent on
  `127.0.0.1:8081`.
- Built the API and web images on the Debian x86_64 host and ran migrations
  through `0004_library`.
- Synchronized the fresh Prowlarr API key with the API service and replaced
  qBittorrent's temporary administrator password with the configured private
  credentials.
- Set the download free-space reserve to 200 GiB after relocating persistent
  data to the 2 TB filesystem. The playback reserve remains 5 GiB.

## Changed files and server paths

- Local documentation: `docs/infrastructure-audit.md` and this report.
- Server application and configuration: `/srv/kadr`.
- Active server persistent data:
  `/srv/photo-storage/kadr/{database,prowlarr,qbittorrent,downloads,playback,library}`.
- Rollback data retained at `/srv/kadr/data`; SQLite online backup retained at
  `/srv/kadr/backups/kadr-pre-storage-move-20261026.db`.
- Docker network: `kadr-internal`.
- Docker containers: `kadr-api-1`, `kadr-web-1`, `kadr-prowlarr-1`, and
  `kadr-qbittorrent-1`.

Photodom files, configuration, mounts, network, and container were not changed
or restarted.

## Checks and results

- Local pre-deployment backend tests: 52 passed.
- Local pre-deployment frontend tests: 25 passed.
- Ruff: passed.
- Vue/TypeScript type check: passed.
- Server `docker compose config --quiet`: passed.
- API and web production builds: passed.
- All four KADR containers: healthy after startup.
- `GET /api/v1/system/health`: HTTP 200 with database status `ok`.
- qBittorrent authentication with the configured KADR account: passed.
- Source and target persistent-data trees matched after the stopped copy;
  both measured 12,807,894 bytes.
- Docker mount inspection confirmed every KADR persistent mount resolves below
  `/srv/photo-storage/kadr`.
- Photodom remained healthy after the KADR restart.

## Known issues

- The new Prowlarr instance has no indexers. Add only authorized indexers via
  an SSH tunnel to its loopback-only UI, then verify `/api/v1/indexers`.
- Prowlarr's startup update check received a Cloudflare block page from
  `servarr.com`; its local service health remains healthy.
- The 2 TB SSD remains a single ext4 partition shared at the filesystem level.
  KADR is isolated by its own owned directory rather than a separate partition.
- Peer ingress for qBittorrent port 6881 is not published. Review the required
  NAT/network behavior separately before changing it.

## Next actions

1. Configure and test an authorized Prowlarr indexer over an SSH tunnel.
2. After an observation period, explicitly approve removal of the retained
   `/srv/kadr/data` rollback copy, or keep it as an additional backup.
3. Run one authorized end-to-end download
   and playback check from a client on the LAN.

## Approved storage relocation

The user subsequently approved a dedicated KADR directory on the existing
2 TB filesystem. The deployment now uses
`KADR_DATA_ROOT=/srv/photo-storage/kadr`. An online SQLite backup was taken
before stopping KADR; the stopped data tree was copied with preserved metadata
and matched the source with `diff`. KADR then restarted with all four services
healthy. No partition or mount was changed.
