# API

All application endpoints use the `/api/v1` prefix.

## `GET /api/v1/system/health`

Checks both the API process and a real SQLite query.

Successful response (`200`):

```json
{"status":"ok","service":"kadr-api","version":"0.1.0","database":"ok"}
```

Database failure (`503`):

```json
{"code":"service_unavailable","message":"Database is unavailable"}
```

FastAPI provides an OpenAPI schema at `/openapi.json` and interactive docs at
`/docs` on the API service.

## Catalogue endpoints

All catalogue responses are normalized by KADR; TMDB credentials and raw
provider errors are never returned to the browser.

| Method and path | Purpose | Parameters |
| --- | --- | --- |
| `GET /movies` | Discover films | `page`, `sort`, `genre`, `year` |
| `GET /series` | Discover series | `page`, `sort`, `genre`, `year` |
| `GET /movies/search` | Search films | `q`, `page`, optional `year` |
| `GET /series/search` | Search series | `q`, `page`, optional `year` |
| `GET /movies/genres` | Film genres | none |
| `GET /series/genres` | Series genres | none |
| `GET /movies/{id}` | Film details, cast, trailer | positive TMDB ID |
| `GET /series/{id}` | Series details, cast, trailer, seasons | positive TMDB ID |
| `GET /series/{id}/seasons/{season_number}` | Normalized season and episode metadata | positive TMDB ID; season `0`-`100` |

`sort` accepts `popular`, `rating`, or `newest`. Pages are limited to TMDB's
first 500 result pages. Invalid query values use FastAPI's validation response.

Season details contain the series and season identity plus normalized episodes:

```json
{
  "id": 501,
  "series_id": 42,
  "number": 2,
  "name": "Сезон 2",
  "overview": "...",
  "air_date": "2025-01-10",
  "poster_url": "https://image.tmdb.org/t/p/w342/example.jpg",
  "episodes": [
    {
      "id": 601,
      "season_number": 2,
      "number": 1,
      "name": "Возвращение",
      "overview": "...",
      "air_date": "2025-01-10",
      "runtime_minutes": 52,
      "still_url": "https://image.tmdb.org/t/p/w500/example.jpg",
      "rating": 8.4
    }
  ]
}
```

This endpoint describes catalogue identity only. It does not expose or infer a
torrent file, playback source, download status, or saved-library state.

Example media page:

```json
{
  "items": [
    {
      "id": 550,
      "kind": "movie",
      "title": "Бойцовский клуб",
      "original_title": "Fight Club",
      "overview": "...",
      "release_date": "1999-10-15",
      "year": 1999,
      "poster_url": "https://image.tmdb.org/t/p/w500/example.jpg",
      "backdrop_url": null,
      "rating": 8.4,
      "popularity": 70.0,
      "genre_ids": [18]
    }
  ],
  "page": 1,
  "total_pages": 1,
  "total_results": 1
}
```

Provider configuration and failure responses use the common error shape:

```json
{"code":"metadata_not_configured","message":"TMDB access token is not configured"}
```

Possible catalogue errors are `404 media_not_found`, `502
metadata_unavailable`, and `503 metadata_not_configured`.

## Source endpoints

### `GET /api/v1/media/{id}/sources`

Runs a user-triggered Prowlarr search. Required query parameter `kind` is
`movie` or `series`. Optional `sort` values are `seeders`, `size`,
`resolution`, `source`, and `title`; `order` is `asc` or `desc`. Series clients
can pass `season_number` from 1 to 100. The server adds an `S01`-style marker
to that search and returns the same number in each normalized release so the
source can be resolved safely later.

```json
{
  "media_id": 42,
  "media_kind": "movie",
  "query": "Dune: Part Two 2024",
  "total": 1,
  "items": [
    {
      "id": "66d83f88a6b5b3d0b9f8f101",
      "title": "Dune.Part.Two.2024.2160p.WEB-DL.HEVC.HDR10",
      "indexer": "Configured indexer",
      "size_bytes": 10737418240,
      "seeders": 24,
      "peers": 3,
      "published_at": "2026-10-20T12:00:00Z",
      "season_number": null,
      "season_numbers": [],
      "protocol": "torrent",
      "resolution": "2160p",
      "source": "WEB-DL",
      "codec": "HEVC",
      "hdr": true,
      "hdr_format": "HDR10",
      "audio": null,
      "language": null,
      "release_type": "web"
    }
  ]
}
```

Unknown title characteristics are `null`; absence of an explicit HDR marker is
reported as `false`. Usenet results are excluded. Raw Prowlarr payloads,
download URLs, magnet links, and API keys are never returned.
`season_number` is the season-specific search context used to resolve the
opaque source again. `season_numbers` is the independently parsed release
coverage used for grouping and may contain a single season, a list, or an
expanded range.

### `GET /api/v1/indexers`

Returns safe summaries of configured Prowlarr indexers: ID, name, enabled
state, protocol, and privacy type. It does not return indexer settings or
credentials.

Source errors use `502 indexer_unavailable` and `503
indexer_not_configured`. Source discovery does not add or download a torrent.

## Torrent Manager endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /media/{id}/torrents` | Resolve an opaque source ID and add it stopped |
| `GET /media/{id}/torrents?media_kind=movie` | Restore the latest task for this title |
| `GET /torrents/{task_id}` | Read real progress, speed, peers, and state |
| `GET /torrents/{task_id}/files` | List torrent files and priorities |
| `GET /torrents/{task_id}/episode-files` | List persisted logical episode/file-ID bindings |
| `DELETE /torrents/{task_id}/files/{file_id}` | Delete one completed cached video |
| `PUT /torrents/{task_id}/selection` | Prioritize one supported video and optionally bind an episode |
| `PUT /torrents/{task_id}/prefetch` | Replace the background episode prefetch queue |
| `POST /torrents/{task_id}/start` | Start after selection and safety checks |
| `POST /torrents/{task_id}/stop` | Stop without deleting data |

The add body is `{"media_kind":"movie","source_id":"<24 hex chars>"}`.
For a release found by a season-specific search it also includes
`"season_number":2`; this makes opaque source resolution repeat the same
search.
Selection keeps the backward-compatible `{"file_id":0}` form. For a series,
it can also persist logical identity with
`{"file_id":0,"season_number":1,"episode_number":2,"catalog_episode_id":123}`;
season and episode numbers must be supplied together. An optional
`variant_label` identifies a quality label without making it part of logical
episode identity. Repeated bindings are idempotent, different files can bind to
different episodes in one task, and several file variants can bind to the same
episode. `selected_file_id` remains the current legacy playback selection.
The episode-files response contains logical and opaque variant IDs plus the
qBittorrent file ID, but never returns a server filesystem path.

Episode prefetch uses
`{"file_ids":[1,2,3]}` (up to 100 supported video files, including an explicitly
selected whole season); an empty list cancels
all queued files except the episode currently selected for playback. Responses include task ID, media identity,
state, progress, byte counts, speeds, peers/seeds, ETA, selected file, and
allowed actions. Source URIs, hashes, credentials, and raw qBittorrent data are
not public API fields.

Torrent errors use `torrent_not_configured` (503), `torrent_unavailable` (502),
`torrent_not_found` (404), `torrent_limit_reached` (409),
`invalid_torrent_file` (422), or `torrent_storage_unavailable` (507).
Individual cached-video deletion never removes the whole torrent task. It is
allowed only for a completed supported video inside KADR's configured download
root. KADR refuses deletion while the task is streaming, while FFmpeg is
preparing that file, or while the task backs a saved library item. A successful
response reports the reclaimed bytes and whether the current player selection
was cleared. Errors use `cache_file_not_found` (404),
`cache_delete_conflict` (409), or `cache_storage_error` (500). There is no
arbitrary whole-torrent delete endpoint.

## Streaming endpoint

### `GET /api/v1/torrents/{task_id}/stream/readiness`

Starts or resumes preparation of the selected file and reports whether the
startup buffer can be opened safely. The response contains `ready` and
`buffer_progress`. KADR checks both the beginning of the adaptive startup
buffer and the tail needed by containers such as MP4 before the player attaches
the media source.

### `GET /api/v1/torrents/{task_id}/stream`

Streams the selected video using Direct Play. The torrent task and video-file
selection must already exist. Without `Range`, the endpoint returns `200 OK`
for the complete file. A single `Range: bytes=START-END`, open-ended range, or
suffix range returns `206 Partial Content`.

Successful responses include `Accept-Ranges: bytes`, exact `Content-Length`,
`Cache-Control: no-store`, and, for partial responses, `Content-Range`. An
invalid, multiple, or unsatisfiable range returns `416` with
`Content-Range: bytes */TOTAL`.

Before sending headers, KADR waits for a bounded initial buffer. It then checks
every chunk's torrent pieces before reading the file. Errors use
`stream_not_ready` (409), `stream_limit_reached` (429), or
`stream_buffer_timeout` (504). If data becomes unavailable after a streaming
response has begun, the connection ends and the player reports a playback
error because HTTP headers can no longer be replaced with JSON.

This Direct Play endpoint does not remux or transcode and does not expose
torrent paths or credentials.

## Compatible-playback endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /torrents/{task_id}/compatible?mode=…` | Explicitly start or reuse preparation |
| `GET /torrents/{task_id}/compatible?mode=…` | Read probe/conversion progress and strategy |
| `GET /torrents/{task_id}/compatible/stream?mode=…` | Stream the ready MP4 with byte ranges |

Preparation requires a selected, fully downloaded video. A `202` response has
`state` (`probing`, `processing`, `ready`, or `failed`), normalized progress,
the chosen `strategy` (`remux`, `audio_transcode`, or `transcode`), detected
video/audio codecs, an optional message, and a stream URL only when ready.
The default `mode=compatible` selects the safest remux/transcode strategy.
`mode=audio_only` preserves the video stream and converts only the first audio
track to AAC stereo; it is intended for a source whose image already works in
the current browser. The two modes use separate cached artifacts.

Only the POST starts FFmpeg; GET is read-only. One preparation runs at a time
by default. Errors use `playback_preparation_failed` or
`playback_preparation_limit` (409). The compatible stream returns `200`/`206`
and the same Range headers as Direct Play; requesting it before completion
returns `playback_artifact_not_ready` (409).

## Library, favorites, and history

| Method and path | Purpose |
| --- | --- |
| `GET /library` | List saved local media and byte sizes |
| `POST /library` | Save one fully downloaded selected file |
| `GET /library/{id}/stream` | Range-stream a saved file without qBittorrent |
| `DELETE /library/{id}` | Delete one inactive saved file |
| `GET /favorites` | List favorites |
| `POST /favorites` | Add an idempotent favorite snapshot |
| `DELETE /favorites/{kind}/{media_id}` | Remove a favorite |
| `GET /history?profile_key=default` | List one profile's server-side watch history |
| `GET /history/{media_id}?media_kind=movie` | Read one title or episode resume position |
| `PUT /history/{media_id}` | Upsert profile/title-or-episode position, duration, and completion |
| `POST /cache/cleanup` | Run the guarded TTL cleanup immediately |
| `GET /system/storage` | Report library/cache counts, bytes, and free space |

Saving requires a task whose selected video is fully downloaded. A series save
may add `season_number`, `episode_number`, and optional `catalog_episode_id` to
the existing media snapshot body. The response includes `file_id` and the
logical `episode` object when applicable. KADR creates
an atomic hard link when possible and otherwise copies to the configured
library root. Repeated or concurrent save requests are idempotent and return
the existing title/episode library item. API responses never expose filesystem paths. Library streaming
supports the same single-range `200`/`206`/`416` contract. Deleting an active
library stream returns `409 library_conflict`; unsafe or unavailable storage
returns `507 library_storage`.

History bodies accept `profile_key` (default `default`) and, for a series,
paired `season_number`/`episode_number` plus optional `catalog_episode_id`.
Episode reads use the same season and episode query parameters. Title-level and
episode-level history rows remain separate, as do rows belonging to different
profiles.

