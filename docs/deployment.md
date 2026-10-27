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

### B2 update on the current Debian host

The audited checkout is `/srv/kadr` and the active KADR-only data root is
`/srv/photo-storage/kadr`. Reconfirm both paths from `.env` before using these
commands; never substitute a Photodom path.

1. Confirm the checkout is clean, inspect the current revision, validate
   Compose, and record KADR service health. Do not restart unrelated services:

   ```bash
   cd /srv/kadr
   git status --short
   git rev-parse HEAD
   docker compose config --quiet
   docker compose ps
   ```

2. Create an online SQLite backup while the current API is still running, then
   validate the backup. The Python command uses only the standard library and
   does not install a host dependency:

   ```bash
   install -d -m 0750 /srv/kadr/backups
   backup=/srv/kadr/backups/kadr-pre-b2-$(date +%Y%m%d-%H%M%S).db
   python3 -c 'import sqlite3,sys; source=sqlite3.connect(sys.argv[1]); target=sqlite3.connect(sys.argv[2]); source.backup(target); target.close(); source.close()' /srv/photo-storage/kadr/database/kadr.db "$backup"
   python3 -c 'import sqlite3,sys; result=sqlite3.connect(sys.argv[1]).execute("PRAGMA integrity_check").fetchone(); print(result[0]); raise SystemExit(0 if result[0] == "ok" else 1)' "$backup"
   ```

3. Fetch the reviewed B2 commit and fast-forward the deployed branch. Stop if
   the checkout has unexpected local changes:

   ```bash
   git fetch origin
   git checkout main
   git pull --ff-only origin main
   ```

4. Validate and test the exact checkout in its existing container toolchain:

   ```bash
   docker compose config --quiet
   docker compose --profile test run --rm --build api-test pytest -p no:cacheprovider
   docker compose --profile test run --rm api-test ruff check --no-cache .
   docker compose --profile test run --rm --build web-test npm test -- --run
   ```

5. Rebuild and replace only KADR's API and web services. The API entrypoint runs
   Alembic through `0006_episode_matcher` before Uvicorn starts; Prowlarr,
   qBittorrent, Photodom, mounts, firewall, and Debian configuration are not
   changed:

   ```bash
   docker compose up -d --build api web
   docker compose ps
   docker compose logs --tail=200 api web
   curl -fsS http://127.0.0.1/api/v1/system/health
   docker compose exec -T api alembic current
   ```

   The expected Alembic revision is `0006_episode_matcher`, all KADR core
   services should be healthy, and the public health request should return
   HTTP 200.

6. Smoke-test an existing movie/library record first, then bind and play two
   different episodes from one torrent task. Confirm one standard exact name is
   mapped automatically and one ambiguous or combined file opens the
   confirmation dialog, then reload and verify the choice is remembered.
   Verify a movie with no source opens `SourceSelector`, hides the raw release
   title until “Технические подробности” is expanded, and reaches the shared
   player after selection. Repeat with an unavailable source and the explicit
   “Другой источник” menu action.
   Confirm each episode restores its own progress and the old library/history
   records remain visible. Keep the legacy source panel in place.

If migration or smoke checks fail, save the API logs, stop only `api` and
`web`, restore the recorded pre-B2 commit and the validated SQLite backup while
the API is stopped, then rebuild those two KADR services. Do not attempt an
Alembic downgrade after episode-level rows have been created: the pre-B2 schema
cannot represent multiple episode rows for one title. Do not use `down -v`,
delete volumes, or alter the active data root during rollback.

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

