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

## Prowlarr does not become healthy

Run `docker compose ps prowlarr` and `docker compose logs --tail=200 prowlarr`.
Its own `/init` process must remain PID 1, so do not add Compose `init: true` to
that service. Confirm `data/prowlarr` permissions and that local port 9696 is
free. Do not delete its database as a repair attempt.

## Source search says Prowlarr is not configured

Open `http://127.0.0.1:9696`, then copy the API key from Settings → General to
`KADR_PROWLARR_API_KEY` in `.env`. Recreate the API with
`docker compose up -d --force-recreate api`. Never expose or commit the key.

## Source search returns no releases

Check `GET /api/v1/indexers`. At least one enabled torrent indexer supporting
movie or TV categories must be configured and pass its test in Prowlarr. An
empty result is valid and is not replaced with mock data. Respect each
indexer's access rules and query limits.

## qBittorrent does not become healthy

Run `docker compose ps qbittorrent` and
`docker compose logs --tail=200 qbittorrent`. Confirm local port 8081 is free
and `data/qbittorrent` plus `data/downloads` are writable by the configured
UID/GID. Do not delete either directory as a repair attempt.

## Torrent Manager says qBittorrent is not configured

Set a private account in qBittorrent's Web UI, copy the same values to
`KADR_QBITTORRENT_USERNAME` and `KADR_QBITTORRENT_PASSWORD`, then recreate the
API container. A rejected login is reported as a controlled 503; credentials
must not be pasted into logs or committed.

## A torrent has no selectable files

Metadata may still be loading. The open task refreshes automatically every five
seconds. KADR accepts only known video extensions and rejects absolute or
parent traversal paths. It does not guess that archives or unknown files are
playable.

## Starting a torrent returns insufficient storage

Check free space on the configured KADR download filesystem. Do not lower
`KADR_MIN_FREE_SPACE_GB` on a deployed host without confirming the cache size,
database headroom, and impact on other services. The development override is
not a production recommendation.

## Adding a source reports the active-download limit

The limit applies only when KADR needs to create a new torrent task. Selecting
a release that is already registered returns the existing task even when the
new-download limit is full. Completed torrents that are seeding do not consume
download slots. Incomplete `downloading`, `queuedDL`, and `stalledDL` tasks do;
stop an unneeded one before adding a truly new release. Stopping is
non-destructive and keeps downloaded data.

## Player remains on “Подготавливаем буфер”

The player polls stream readiness every five seconds and shows the percentage
of required startup pieces. Confirm that peers are present if that percentage
does not change. KADR does not attach the browser media source or send
unavailable sparse bytes until the beginning and required container tail are
ready. It enables qBittorrent's sequential and first/last-piece modes for
incomplete streams. A distant seek can still time out because qBittorrent's Web
API cannot assign priority to an arbitrary piece range.

If the beginning remains unavailable while later pieces are downloading, make
sure the selected file has normal priority (`1`), not maximal priority (`7`).
Maximal file priority can conflict with sequential piece ordering in
qBittorrent 5.x. Opening the player reapplies the safe priority automatically.

## Player reports that the video stream cannot be opened

Inspect the readiness and stream requests plus API logs. A 409
means no usable selected file, 429 means either the distinct-task limit or the
per-task parallel Range limit was reached, 504 means required pieces did not
arrive, and 416 means the browser or client sent an invalid range. A failed
media decode with successful HTTP ranges usually means the browser does not
support the container or codec. Wait for the selected file to finish, then use
“Совместимая версия”. FFmpeg is intentionally not started automatically.
After preparation succeeds, subsequent playback attempts automatically reuse
the compatible artifact. Refresh a page that was already open while the
artifact was being prepared.

## Compatible-version preparation fails

The file must be completely downloaded. A preparation-limit response means
another FFmpeg job is running; wait for it to finish. For other failures,
inspect `docker compose logs --tail=200 api`, verify `ffmpeg -version` and
`ffprobe -version` inside the API container, and confirm `data/playback` is
writable by `KADR_UID:KADR_GID`. Do not make `data/downloads` writable to the
API as a workaround.

An insufficient-space message includes the estimated output size plus the
configured `KADR_PLAYBACK_MIN_FREE_SPACE_GB` reserve. Reclaim only confirmed
KADR-owned cache data through a reviewed process; do not run broad Docker or
filesystem cleanup commands.

The compatible profile uses the first audio stream, AAC-LC stereo, and H.264
8-bit video when conversion is needed. Alternate tracks, embedded subtitles,
HDR tone mapping, and every browser/device combination are not yet supported.

## Resume position is missing

Stage 6 stores resume state in SQLite and keeps browser-local state as a
fallback. Check `GET /api/v1/history/{media_id}?media_kind=...` and API logs.
Positions under five seconds and completed titles intentionally do not prompt
for resume.

## Saving to the library is unavailable

The selected file must reach 100%. Confirm `data/library` is writable by the
configured KADR UID/GID and remains an isolated KADR-only directory. Do not
make unrelated paths writable as a workaround.

## A saved file cannot be deleted

Close every player using that item and retry. KADR rejects deletion while a
library Range response is active and refuses paths outside
`KADR_LIBRARY_ROOT`; never bypass these checks.

## Cache cleanup did not remove a torrent

Cleanup removes only stopped, unsaved KADR tasks older than
`KADR_CACHE_TTL_HOURS`. Active playback, active downloading, and tasks tied to
a saved library record are protected.

