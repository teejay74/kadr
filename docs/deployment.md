# Deployment

## Local Stage 1

1. Copy `.env.example` to `.env` and select an unused `KADR_HTTP_PORT`.
2. Ensure `data/database` is writable by `KADR_UID:KADR_GID`.
3. Run `docker compose config --quiet`.
4. Run `docker compose up --build -d`.
5. Wait for `docker compose ps` to report both core services healthy.
6. Check `curl http://localhost:8180/api/v1/system/health` and load the UI.

`docker compose down` stops only this Compose project. Never use `down -v` in a
normal update.

## Mandatory Debian preflight

Stage 1 was prepared and tested locally; it has not touched the working Debian
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

