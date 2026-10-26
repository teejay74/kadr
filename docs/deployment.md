# Deployment

## Local Stage 6

1. Copy `.env.example` to `.env` and select an unused `KADR_HTTP_PORT`.
2. Create a TMDB API Read Access Token and set `KADR_TMDB_ACCESS_TOKEN` in
   `.env`. Do not commit or paste the token into frontend configuration.
3. Start Prowlarr with `docker compose up -d prowlarr`, open
   `http://127.0.0.1:9696`, complete its authentication setup, and add an
   indexer you are authorized to use.
4. Copy the Prowlarr API key from Settings → General into
   `KADR_PROWLARR_API_KEY` in `.env`.
5. Start qBittorrent, set a private Web UI username/password, and copy them to
   `KADR_QBITTORRENT_USERNAME` and `KADR_QBITTORRENT_PASSWORD`. Follow
   [qbittorrent.md](qbittorrent.md); do not retain the temporary password.
6. Ensure `data/database`, `data/prowlarr`, `data/qbittorrent`,
   `data/downloads`, `data/playback`, and `data/library` are writable by the configured UID/GID.
   Set `KADR_DATA_ROOT` to an audited KADR-only host directory when persistent
   media should live outside the application checkout. Do not point it at a
   Photodom directory or filesystem root; use a separately owned child
   directory created explicitly for KADR.
   The API receives downloads read-only and writes only generated media under
   playback. Set both free-space floors for the audited host; the download
   default is 200 GB and the playback-cache reserve is 5 GB.
7. Run `docker compose config --quiet`.
8. Run `docker compose up --build -d`.
9. Wait for `docker compose ps` to report all five core services healthy.
10. Check `curl http://localhost:8180/api/v1/system/health`, then load the UI and
   verify one catalogue and detail request.
11. Select a supported video, open the player, and verify `200`, `206`, and a
    forward seek while watching API and qBittorrent logs. Tune stream settings
    only after measuring the target host and network.
12. On a fully downloaded incompatible fixture, explicitly request
    “Совместимая версия”, verify FFmpeg progress, probe the generated MP4 for
    H.264/AAC, and test a ranged compatible-stream response. Full transcodes
    should be load-tested on the target CPU before regular use.

`docker compose down` stops only this Compose project. Never use `down -v` in a
normal update.

## Mandatory Debian preflight

Stages 1-6 were prepared and tested locally; they have not touched the working
Debian server. Before server deployment, perform read-only checks for OS/architecture,
Docker/Compose versions, running containers and Compose projects, listening
ports, memory/load, free space/inodes, mount filesystem/type/options, and the
intended KADR directory ownership. Confirm that port 8180 and the chosen paths
do not overlap Photodom. Record the result before creating anything.

Do not change mounts, firewall, Docker daemon settings, Photodom, or disks as
part of this preflight. Any required infrastructure change needs separate user
approval and a rollback plan.

## Update outline

Validate configuration, back up `kadr.db` with SQLite's online backup method,
build pinned images, run migrations, verify both health checks, and retain the
previous application image and database backup for rollback.

Prowlarr port `9696` is bound to `127.0.0.1`, not the LAN. For remote Debian
administration, use an SSH tunnel rather than changing the bind address or
opening a firewall port. Back up `data/prowlarr` together with the KADR database
before upgrades. The image is pinned by multi-architecture digest; update it
only as a reviewed deployment change.

qBittorrent port `8081` is likewise loopback-only and must remain off the LAN.
Its BitTorrent listen port is not published by the development Compose file;
review the actual network/NAT requirement separately before production changes.
Back up its configuration, but treat downloaded cache data according to the
later Stage 6 lifecycle policy.

The API image includes FFmpeg and `ffprobe`. Compatible output is a separate
bind mount at `data/playback`; back it up only if regenerating files would be
undesirable. Do not point that root at Photodom. CPU/RAM limits and the default
single active job are safety baselines, not proof of capacity on the Debian
host.

FlareSolverr is internal-only and must not publish port 8191. Configure it in
Prowlarr under Settings → Indexers → Indexer Proxies with host
`http://flaresolverr:8191`. Assign a dedicated tag to the proxy and only to
indexers that require Cloudflare handling. FlareSolverr starts a browser per
request, so keep concurrency low and retain the configured memory, shared-memory,
and tmpfs limits unless target-host measurements justify a change.

