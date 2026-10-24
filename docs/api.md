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

`sort` accepts `popular`, `rating`, or `newest`. Pages are limited to TMDB's
first 500 result pages. Invalid query values use FastAPI's validation response.

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
metadata_unavailable`, and `503 metadata_not_configured`. Torrent, download,
streaming, playback, and library mutation endpoints do not exist in Stage 3.

## Source endpoints

### `GET /api/v1/media/{id}/sources`

Runs a user-triggered Prowlarr search. Required query parameter `kind` is
`movie` or `series`. Optional `sort` values are `seeders`, `size`,
`resolution`, `source`, and `title`; `order` is `asc` or `desc`.

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

### `GET /api/v1/indexers`

Returns safe summaries of configured Prowlarr indexers: ID, name, enabled
state, protocol, and privacy type. It does not return indexer settings or
credentials.

Source errors use `502 indexer_unavailable` and `503
indexer_not_configured`. Source discovery does not add or download a torrent.

