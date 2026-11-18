# TMDB poster delivery through KADR — 2026-11-18

## Completed work

This Stage 2/7 maintenance increment routes TMDB posters, backdrops, seasons and
stills through the versioned KADR API. Strict size/filename validation, a fixed
upstream host, no redirects or URL parameters, bounded responses, MIME/signature
checks and full HTTPS verification protect the endpoint. Google DNS-JSON over
HTTPS uses a configurable bootstrap address for the resolver; CDN addresses
remain dynamic. DNS caching respects answer TTL up to 300 seconds.

The dedicated image client ignores environment proxies, limits active downloads
to four, and applies a 12-second total fetch timeout. Successful images persist
in a dedicated 128 MiB disk cache for 30 days by default, with browser caching.
Filesystem work runs in worker threads. Same-image requests share a striped
lock. Cache failures are logged; unsuccessful upstream responses are not cached.

Web PosterImage handles failed images and translates legacy TMDB links from
persisted data. Android already consumes API image URLs; ServerAddress now also
translates legacy links before Coil receives them. Kinopoisk images keep their
existing provider URLs. No playback or router/browser DNS settings change.

## Changed files

- Backend: config, lifespan, API router, new posters endpoint, PosterManager,
  PosterCacheRepository, catalogue image builder and backend regression tests.
- Web: shared PosterImage/imageUrl, catalogue and details components, episode
  images, library/history pages, placeholder CSS and regression tests.
- Android: ServerAddress and its unit tests.
- Configuration: `.env.example`, `docker-compose.yml`.
- Documentation: README, architecture, deployment, API, storage, streaming,
  troubleshooting and Android TV instructions.

## Checks and results

- Backend: 188 tests passed.
- Frontend: 111 tests passed; strict TypeScript and production build passed.
- Ruff and Compose configuration validation passed.
- Android TV: 31 JVM tests passed; debug APK assembled in the existing working
  tree. Existing unrelated player changes were present and are excluded from
  this poster commit.
- Real container request resolved the CDN through Google DoH, preserved TLS/SNI,
  and downloaded a 62,184-byte WebP response from TMDB successfully.
- Debian read-only preflight: all five KADR services healthy; about 6 GiB RAM
  available, 103 GiB root free, 1.1 TiB free on the API data filesystem; API UID
  1000 has access to persistent data. Existing database backups were inspected.
- Deployment, browser acceptance and TV emulator checks follow the code commit.

## Known issues and next actions

The physical Android 11 television is not connected through ADB. Verify its
catalogue and movie/series details after deploying the API. Updated API links
already work with the existing APK; legacy persisted absolute links also need
the new client helper. Google TV emulator validation is planned. One API worker
per cache directory is supported. Cached images remain usable during an outage
until their TTL; uncached failures render the web placeholder. An upstream
outage is tested with isolated test doubles, without changing production DNS.
