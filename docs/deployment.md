# Deployment

## Local Stage 4

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
6. Ensure `data/database`, `data/prowlarr`, `data/qbittorrent`, and
   `data/downloads` are writable by the configured UID/GID. Set the free-space
   floor appropriate for the audited host; production default is 200 GB.
7. Run `docker compose config --quiet`.
8. Run `docker compose up --build -d`.
9. Wait for `docker compose ps` to report all four core services healthy.
10. Check `curl http://localhost:8180/api/v1/system/health`, then load the UI and
   verify one catalogue and detail request.

`docker compose down` stops only this Compose project. Never use `down -v` in a
normal update.

## Mandatory Debian preflight

Stages 1-4 were prepared and tested locally; they have not touched the working
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

