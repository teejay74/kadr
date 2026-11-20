# TMDB network recovery — 2026-11-20

## Completed work

Stage 2/7 maintenance: extracted the poster DNS-JSON resolver into a shared
TMDBResolver and added a dedicated metadata HTTP transport. Both TMDB origins
now resolve through the configured DoH endpoint and public-address validation.
Connections preserve Host and TLS SNI, retain certificate checks, respect DNS
TTL and timeouts, and never pin CDN/API IPs. Existing `KADR_POSTER_DOH_*` settings
remain compatible. No router, browser, container-wide DNS or other service
network settings are changed.

Source search permits existing cached partial catalogue details when full TMDB
metadata is unavailable, retaining the media ID and kind. Missing metadata still
returns a controlled error. Poster validation logs now include the rejection
reason; metadata transport logs omit authentication headers and tokens.

## Changed files

- `backend/app/services/network/{__init__,tmdb}.py`: resolver and transport.
- `backend/app/main.py`: metadata-client transport wiring.
- `backend/app/services/posters/manager.py`: shared resolver and diagnostics.
- `backend/app/services/sources/search.py`: cached-metadata fallback and protocol.
- `backend/tests/test_{tmdb_network,posters,sources}.py`: regression checks.
- README, architecture, deployment, API and troubleshooting documentation.

## Checks and results

- Backend: 193 tests passed; Ruff passed. No frontend or Android code changed.
- Tests cover metadata DoH routing, Host/SNI preservation, TTL reuse, rejection
  of local IPs and unexpected origins, controlled DoH HTTP errors, and source
  search using partial cached metadata. Existing image/cache safety tests pass.
- Read-only Debian preflight: all five KADR services healthy, clean deployment
  checkout, about 5.5 GiB available RAM, 103 GiB root free and 1.1 TiB data free.
  API UID 1000 can access persistent data; retained backups inspected.
- A real container transport check to the TMDB API is run before deployment;
  without credentials the expected authenticated endpoint response is HTTP 401.
- Deployment validation and source-search results are recorded below afterwards.

## Known issues and next actions

The exact cause of earlier poster ValueError events cannot be reconstructed
from the old logs. This change records explicit validation reasons for future
incidents. An outage affecting both configured DoH providers can still prevent
uncached requests. Cached metadata/images mitigate outages but do not invent
missing data. Retain the existing backup and inspect health/logs after rollout.

## Additional finding before deployment

The real container check reproduced a Google DoH DNS response containing
`127.0.0.1` for the TMDB API, while independent Cloudflare DoH returned public
addresses. The resolver now tries a configurable independent Cloudflare
fallback when the primary lookup fails validation or network I/O. Public-IP
validation applies to both providers. A regression test covers primary loopback
answers, successful fallback and reuse of the validated DNS cache.
