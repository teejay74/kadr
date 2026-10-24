# Deployment

## Local Stage 3

1. Copy `.env.example` to `.env` and select an unused `KADR_HTTP_PORT`.
2. Create a TMDB API Read Access Token and set `KADR_TMDB_ACCESS_TOKEN` in
   `.env`. Do not commit or paste the token into frontend configuration.
3. Start Prowlarr with `docker compose up -d prowlarr`, open
   `http://127.0.0.1:9696`, complete its authentication setup, and add an
   indexer you are authorized to use.
4. Copy the Prowlarr API key from Settings → General into
   `KADR_PROWLARR_API_KEY` in `.env`.
5. Ensure `data/database` and `data/prowlarr` are writable by the configured
   UID/GID.
6. Run `docker compose config --quiet`.
7. Run `docker compose up --build -d`.
8. Wait for `docker compose ps` to report all three core services healthy.
9. Check `curl http://localhost:8180/api/v1/system/health`, then load the UI and
   verify one catalogue and detail request.

`docker compose down` stops only this Compose project. Never use `down -v` in a
normal update.

## Mandatory Debian preflight

Stages 1-3 were prepared and tested locally; they have not touched the working
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

