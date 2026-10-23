# Deployment

## Local Stage 2

1. Copy `.env.example` to `.env` and select an unused `KADR_HTTP_PORT`.
2. Create a TMDB API Read Access Token and set `KADR_TMDB_ACCESS_TOKEN` in
   `.env`. Do not commit or paste the token into frontend configuration.
3. Ensure `data/database` is writable by `KADR_UID:KADR_GID`.
4. Run `docker compose config --quiet`.
5. Run `docker compose up --build -d`.
6. Wait for `docker compose ps` to report both core services healthy.
7. Check `curl http://localhost:8180/api/v1/system/health`, then load the UI and
   verify one catalogue and detail request.

`docker compose down` stops only this Compose project. Never use `down -v` in a
normal update.

## Mandatory Debian preflight

Stages 1-2 were prepared and tested locally; they have not touched the working Debian
server. Before server deployment, perform read-only checks for OS/architecture,
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

