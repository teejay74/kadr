# Stage 6 extension report — FlareSolverr

## Completed work

- Added digest-pinned FlareSolverr 3.5.2 for Cloudflare-protected Prowlarr
  indexers.
- Kept port 8191 internal to the KADR network.
- Runs as the image's unprivileged `flaresolverr` user with
  `no-new-privileges`, a health check, restart policy, CPU/RAM limits, 256 MiB
  shared memory, and a 256 MiB RAM-backed `/tmp` ceiling.
- Added configurable resource values and documented tag-scoped Prowlarr setup.
- Defaulted logging to `warning` because `info` logs request bodies and can
  expose indexer credentials.

## Changed files

- `.env.example`
- `docker-compose.yml`
- `README.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/prowlarr.md`
- `docs/troubleshooting.md`
- `docs/stage-6-flaresolverr-report.md`

## Checks

- `docker compose config --quiet`: passed on the Debian host.
- Backend Pytest suite: 52 passed.
- Frontend Vitest suite: 25 passed.
- FlareSolverr 3.5.2: healthy, internal HTTP ready, unprivileged user, no host
  port binding, approximately 128 MiB idle memory before log hardening.
- Prowlarr runtime configuration: `flaresolverr` tag and tag-scoped
  `http://flaresolverr:8191/` proxy created.
- `https://kinozal.guru/`: Cloudflare challenge solved, HTTP 200.
- `https://kinozal.me/`: challenge timed out after 60 seconds.
- KADR web/API: HTTP 200. Photodom remained available and was not restarted.
- Recreated only FlareSolverr with `LOG_LEVEL=warning`; a repeat Kinozal Guru
  challenge returned HTTP 200 and the container log remained empty.

## Known issues

- Use Kinozal's `.guru` base URL on this host; `.me` remains inaccessible.
- Prowlarr's proxy Test calls `prowlarr.servarr.com`, which is blocked for this
  server IP and therefore reports a false-negative failure. The target Kinozal
  Guru request succeeds through the same Prowlarr-to-FlareSolverr path.
- Each request launches Chromium and temporarily increases RAM/CPU use.
- No proxy tag or indexer credentials are provisioned in Git.
- An initial `info`-level diagnostic logged an indexer login request. The old
  container was replaced to remove that Docker log, and the affected indexer
  password should be rotated.

## Next actions

Add Kinozal with the `.guru` base URL and the existing `flaresolverr` tag, then
test and save it. Rotate the Kinozal password before storing the indexer.
