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

## Unified playback resolution

### `POST /api/v1/playback/resolve`

Resolves the concrete playback source for both films and series episodes. The
backend prefers an available saved-library item, then a persisted torrent file
variant. It checks stream piece readiness and restores the matching profile and
episode resume position. It does not search Prowlarr and does not infer an
episode from a torrent filename.

Film request:

```json
{"media_kind":"movie","media_id":42,"profile_key":"default"}
```

Episode request:

```json
{
  "media_kind": "series",
  "media_id": 42,
  "season_number": 2,
  "episode_number": 3,
  "catalog_episode_id": 603,
  "profile_key": "default"
}
```

`season_number` and `episode_number` must be supplied together and are rejected
for films. A successful resolution uses one of four application states:

- `ready`: the returned library or torrent stream can be opened;
- `buffering`: the exact torrent file is selected but its startup pieces are
  still being prepared;
- `source_required`: no persisted source exists, so the client may offer manual
  source selection;
- `unavailable`: a persisted source exists but cannot currently be opened, so
  the client should explain the failure and offer another source.

```json
{
  "status": "buffering",
  "source": "torrent",
  "stream_url": "/api/v1/torrents/7ad8/stream",
  "task_id": "7ad8",
  "file_id": 4,
  "library_item_id": null,
  "resume_position_seconds": 125,
  "buffer_progress": 0.62,
  "download_progress": 0.18,
  "download_state": "downloading",
  "download_speed_bytes": 2500000,
  "message": null
}
```

The public response never contains a filesystem path, torrent URI, hash, or
credential. A `200` response with `source_required` or `unavailable` is a
controlled workflow state rather than a transport failure.

For a newly selected film torrent with no legacy `selected_file_id`, the
resolver asks Torrent Manager to select the largest safe supported video on the
backend before checking piece readiness. The browser never chooses a concrete
torrent file from its name. Series still require a persisted logical
episode/file binding, normally created by Episode Matcher.

### `POST /api/v1/playback/next`

Finds the next series episode from TMDB season metadata and resolves its
playback source. The client supplies the current catalog episode plus optional
current task/file identity. The server follows catalog order, including season
boundaries, and prefers a confirmed variant from the current torrent task. It
never computes the result by blindly incrementing an episode number.

### `POST /api/v1/playback/next/prefetch`

Finds the same metadata-owned next episode but only enables its single
confirmed file in the current torrent task alongside the actively selected
file. It does not resolve another release and does not queue a season. The
response reports `prefetched`; missing bindings remain `source_required`.
When current and next episodes map to one combined file, `combined_file` is
true and KADR explicitly declines to promise a precise seek without stored
time boundaries.

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

`GET /api/v1/torrents` returns up to 100 recent KADR-owned torrent tasks in
database recency order. Torrent state is joined with one qBittorrent list
request, avoiding per-card polling. A persisted task missing from qBittorrent
is returned with state `unavailable` and no start/stop actions. The response
does not expose torrent hashes, source URIs, credentials, or filesystem paths.

| Method and path | Purpose |
| --- | --- |
| `POST /media/{id}/torrents` | Resolve an opaque source ID and add it stopped |
| `GET /media/{id}/torrents?media_kind=movie` | Restore the latest task for this title |
| `GET /torrents/{task_id}` | Read real progress, speed, peers, and state |
| `GET /torrents/{task_id}/files` | List torrent files and priorities |
| `GET /torrents/{task_id}/episode-files` | List persisted logical episode/file-ID bindings |
| `POST /torrents/{task_id}/episode-matches/analyze` | Analyze and safely persist unique exact episode matches |
| `PUT /torrents/{task_id}/episode-matches` | Confirm one or more episode mappings per file |
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
qBittorrent file ID, matching confidence, confirmation provenance, and optional
future segment index, but never returns a server filesystem path.

Episode analysis reads the full relative torrent path and recognizes `S01E02`,
`1x02`, `Season 1 Episode 2`, `Сезон 1 Серия 2`, combined markers, and bounded
ranges. It validates episode identities against TMDB and may use a duration
already supplied by the torrent adapter as supporting evidence; it never
downloads or probes a file just to match it. The response classifies each video
as `exact`, `probable`, or `ambiguous`. Only an exact, unique, conflict-free
result is stored automatically. Probable, ambiguous, conflicting, metadata-
unverified, and unsafe-path results require user action or remain unbound.

Confirmation accepts, for example:

```json
{
  "mappings": [
    {
      "file_id": 7,
      "episodes": [
        {"season_number": 1, "episode_number": 1},
        {"season_number": 1, "episode_number": 2}
      ]
    }
  ]
}
```

This represents a combined file without claiming time boundaries for its
individual episodes. A logical episode may also have several file variants.
Automatic concatenation of several files is not implemented.

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
startup buffer can be opened safely. The response contains `ready`,
`buffer_progress`, `file_progress`, `download_state`, and
`download_speed_bytes`. `file_progress` always belongs to the selected video,
not the aggregate set of current and prefetched files. KADR checks the
beginning of the adaptive startup buffer and, only for containers that may
depend on trailing metadata such as MP4/MOV or AVI, a bounded tail probe before
the player attaches the media source. MKV/WebM and transport streams can start
from their available beginning.

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

## Audio and subtitle track discovery

| Method and path | Purpose |
| --- | --- |
| `GET /torrents/{task_id}/tracks` | Inspect the completed selected torrent file |
| `PUT /torrents/{task_id}/tracks/preferences` | Save this profile's selected tracks |
| `POST /torrents/{task_id}/tracks/{track_id}/subtitle` | Explicitly prepare one text subtitle |
| `GET /library/{id}/tracks` | Inspect one saved library file |
| `PUT /library/{id}/tracks/preferences` | Save this profile's selected tracks |
| `POST /library/{id}/tracks/{track_id}/subtitle` | Explicitly prepare one text subtitle |

Track discovery is read-only and on-demand. Torrent inspection requires the
selected file itself to be 100% complete; KADR never downloads or probes every
file in a season for this endpoint. The server runs a bounded `ffprobe` process
and returns separate `audio_tracks` and `subtitle_tracks` arrays. Each entry
contains an opaque exact `id`, semantic `preference_key`, ffprobe
`stream_index`, language when known, codec, optional title, default/forced and
hearing-impaired flags, audio channel metadata, and a delivery capability.
GET accepts `profile_key` (default `default`) and also returns
`selected_audio_track_id`, `selected_subtitle_track_id`, and
`subtitles_enabled` after resolving stored semantic preferences against this
file's current tracks.

The exact ID includes the stream index and identifies one stream in this file.
The preference key excludes that index, so a later preferences stage can match
the same language/label/codec semantics even when another file orders its
streams differently. Text subtitles report `external_webvtt`, bitmap subtitles
report `burn_in_required`, and unknown codecs report `unsupported`. Missing
titles remain `null`.
Failures use `playback_tracks_unavailable` (409). Unsafe paths continue to use
the existing torrent/library storage errors. Track discovery never starts
FFmpeg and does not change the Direct Play Range contract.

Preference PUT bodies contain `profile_key`, optional `audio_track_id`,
optional `subtitle_track_id`, and `subtitles_enabled`. Enabling subtitles
requires a subtitle ID from this file. KADR validates submitted opaque IDs
against the freshly discovered list before persistence; an ID belonging to a
different file returns `422 invalid_playback_track`. The database stores the
semantic key plus normalized language/title/codec, not a numeric stream index.
Exact semantic identity is preferred on later files, followed by conservative
language/title/codec matching and then that file's default stream. Profiles are
independent, and disabling subtitles retains the last semantic subtitle choice.

The subtitle POST is the only operation that starts extraction. It re-probes
the current source, rejects stale/cross-file or non-text track IDs, invokes a
bounded FFmpeg process for that exact stream, and returns a same-origin WebVTT
URL. Outputs are atomic and cached by source size, modification time, and track
identity. Opening track discovery, saving a preference, and ordinary Direct
Play do not start FFmpeg. The returned WebVTT GET uses
`/torrents/{task_id}/subtitles/{artifact_id}.vtt` or the corresponding library
path. Failures use `playback_subtitle_unavailable` (409).

## Compatible-playback endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /torrents/{task_id}/compatible?mode=…&track_id=…` | Explicitly start or reuse preparation |
| `GET /torrents/{task_id}/compatible?mode=…&track_id=…` | Read probe/conversion progress and strategy |
| `DELETE /torrents/{task_id}/compatible?mode=…&track_id=…` | Cancel a queued preparation before it starts |
| `GET /torrents/{task_id}/compatible/stream?mode=…&track_id=…` | Stream the ready MP4 with byte ranges |

Preparation requires a selected, fully downloaded video. A `202` response has
`state` (`queued`, `probing`, `processing`, `ready`, or `failed`), normalized progress,
the chosen `strategy` (`remux`, `audio_transcode`, or `transcode`), detected
video/audio codecs, an optional one-based `queue_position`, an optional message,
and a stream URL only when ready.
The default `mode=compatible` selects the safest remux/transcode strategy.
`mode=audio_only` preserves the video stream and converts only the first audio
track to AAC stereo; it is intended for a source whose image already works in
the current browser. `mode=audio_track` requires an opaque `track_id` returned
by the current file's track endpoint. KADR re-probes the source, rejects stale
or cross-file IDs with `422 invalid_playback_track`, maps that exact audio
stream, copies the video, and converts the selected audio to AAC stereo. Each
selected track uses a separate cache artifact and job identity; the response
echoes `track_id`. These modes do not make an unsupported video codec playable.

Only the POST creates a job; GET is read-only. One preparation runs at a time
by default, while up to five distinct jobs wait in a bounded in-memory FIFO
queue. Repeating the same request reuses its active or queued job. DELETE only
cancels a job that has not started. A process restart drops queued jobs but
keeps completed cache artifacts. Errors use `playback_preparation_failed` or
`playback_preparation_limit` (409 when the queue is full). The compatible stream returns `200`/`206`
and the same Range headers as Direct Play; requesting it before completion
returns `playback_artifact_not_ready` (409).

## Library, favorites, and history

| Method and path | Purpose |
| --- | --- |
| `GET /library` | List saved local media and byte sizes |
| `POST /library` | Save one fully downloaded selected file |
| `GET /library/{id}/stream` | Range-stream a saved file without qBittorrent |
| `GET /library/{id}/tracks` | Inspect audio/subtitle streams on demand |
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

