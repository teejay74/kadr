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

## A series season has no episode list

Retry the season from the series page, then inspect the request to
`GET /api/v1/series/{id}/seasons/{season_number}` and the API logs. A controlled
metadata error means TMDB is unavailable and no cached season response exists.
An empty episode list is preserved as an honest provider result; KADR does not
generate placeholder episodes. Episode metadata is independent of torrent file
discovery, so Prowlarr and qBittorrent settings do not repair this error.

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

## Indexer is blocked by Cloudflare

Confirm the failure in Prowlarr logs and try another base URL shipped by the
current indexer definition. For a browser challenge, configure the internal
FlareSolverr endpoint `http://flaresolverr:8191` as an Indexer Proxy and use a
matching tag on the proxy and indexer. If FlareSolverr also receives a blocked
page, the site is rejecting the public IP; changing credentials or repeatedly
retrying will not help.

Keep `KADR_FLARESOLVERR_LOG_LEVEL=warning`. At `info`, FlareSolverr logs full
request bodies, which can include indexer login credentials.

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
ready. The shared player stops automatic readiness polling after twelve checks
(about one minute) and offers an explicit retry instead of loading forever. It
enables qBittorrent's sequential and first/last-piece modes for incomplete
streams. A distant seek can still time out because qBittorrent's Web API cannot
assign priority to an arbitrary piece range.

If the beginning remains unavailable while later pieces are downloading, make
sure the selected file has normal priority (`1`), not maximal priority (`7`).
Maximal file priority can conflict with sequential piece ordering in
qBittorrent 5.x. Opening the player reapplies the safe priority automatically.

## “Выберите источник” or “Сохранённый источник сейчас недоступен” appears

The unified resolver returns `source_required` when no saved item or persisted
torrent-file binding exists. KADR opens the source-selection modal; retry its
search if the indexer was temporarily unavailable. The retained source panel
remains available as a manual fallback during C2 acceptance. For a series,
confirm the selected file was bound to the exact episode with
`GET /api/v1/torrents/{task_id}/episode-files`. The resolver itself never
guesses an episode: the separate Episode Matcher first validates filenames
against TMDB and persists only unique exact matches.

`unavailable` means a saved or bound source exists but its file, torrent task,
storage, or qBittorrent state cannot currently be used. Check
`docker compose logs --tail=200 api`, the relevant task status, and KADR-owned
mount permissions. Choose another source if the old one is gone. Do not repair
this by exposing internal services or making unrelated host paths writable.

If a chosen magnet is registered but its file list is not ready within the
bounded modal wait, KADR keeps the modal open and asks you to retry after a few
seconds. It does not poll indefinitely or start a whole season. For a film,
the backend chooses the largest safe supported video; for a series, Episode
Matcher must confirm the requested episode before the unified resolver starts
playback.

## Episode Matcher asks for confirmation or cannot save a match

`probable` means the path or duration is useful but not strong enough for safe
automatic binding. `ambiguous` means several candidates, a conflict, missing
TMDB evidence, or an unsafe path. Select every episode actually contained in
the file and save once; KADR reuses that torrent/file mapping after restart.
Combined files can map to several episodes, but without stored time boundaries
KADR cannot jump precisely to the second episode. If TMDB is unavailable,
retry after metadata access is restored; do not bypass validation by editing
SQLite. Absolute paths, `..`, control characters, and Windows drive paths are
rejected rather than offered for confirmation.

## The next-episode overlay is missing or cannot continue

KADR asks the backend for catalog order only after a series episode ends. If
TMDB is unavailable, inspect API logs and restore metadata access. A
`source_required` result means Episode Matcher has no confirmed file binding
for that next logical episode; choose a source in the normal modal. A combined
file warning is intentional: without stored time boundaries KADR cannot know
where the second episode begins, so it does not restart the same file and call
that an exact transition.

Near-end prefetch is opportunistic and limited to one confirmed next file in
the current torrent task. Failure does not interrupt current playback. If it
does not start, verify the next episode binding and qBittorrent availability;
do not enable a whole season as a workaround.

## A task is marked “Нет в qBittorrent” on Downloads

The task still exists in KADR's SQLite history, but its torrent hash was not
present in the single qBittorrent status response. Start/stop and file actions
are disabled for that row. Check qBittorrent availability and its data volume;
do not edit SQLite or expose the qBittorrent Web UI to the network. A normal
source selection can create or reuse an available task.

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
fallback. For a series episode, check
`GET /api/v1/history/{media_id}?media_kind=series&season_number=...&episode_number=...`;
add `profile_key=...` when using a non-default profile. Confirm that
`GET /api/v1/torrents/{task_id}/episode-files` contains the selected file's
episode binding. A legacy file without a binding deliberately continues to use
title/task-level resume state rather than guessing an episode. Check API logs
for persistence errors.
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

