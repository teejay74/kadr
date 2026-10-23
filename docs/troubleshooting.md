# Troubleshooting

## Containers do not become healthy

Run `docker compose ps` and `docker compose logs --tail=200`. An API startup
failure commonly means that `data/database` is not writable by the configured
UID/GID or an Alembic migration failed.

## Port is already in use

Set `KADR_HTTP_PORT` in `.env` to a verified unused LAN port and rerun
`docker compose up -d`. Do not stop or reconfigure an existing service merely
to claim its port.

## UI says the API is unavailable

Check `/api/v1/system/health`, then inspect API and web logs. nginx resolves the
API by the Compose service name `api`; both services must share `kadr-internal`.

## Database is locked

Confirm the DB is on a local filesystem, no manual tool holds a long write
transaction, and only the KADR API writes it. Do not delete WAL/SHM files from a
running database.

## Catalogue says TMDB is not configured

Set a valid TMDB API Read Access Token as `KADR_TMDB_ACCESS_TOKEN` in `.env`,
then recreate the API container with `docker compose up -d --build api`. The
token is a bearer token, not the shorter v3 API key. Never place it in frontend
environment variables or commit `.env`.

## Catalogue returns a metadata provider error

Check API logs for the status category without exposing credentials. Verify
outbound DNS/HTTPS, the token, and TMDB availability. KADR serves a previously
cached response during a temporary provider outage when one exists; otherwise
it returns a controlled `502`. Do not increase polling frequency as a remedy.

