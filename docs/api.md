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
`/docs` on the API service. Authentication and the domain endpoints listed in
the specification are future stages and must not be treated as available.

