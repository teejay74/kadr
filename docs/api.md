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
streaming, playback, and library mutation endpoints do not exist in Stage 2.

