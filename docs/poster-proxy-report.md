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
- Exact committed Android source was also built in an isolated checkout:
  29 JVM tests passed, APK assembled and installed in the Google TV emulator.
- Commit `95a6298` was pushed to `origin/main` and deployed on Debian by
  rebuilding/recreating only KADR API and web. Other services were not restarted.
  A verified online SQLite backup was created first at
  `/srv/kadr/backups/kadr-pre-posters-20261118-215935.db`.
- After deployment all five KADR services were healthy, the API reported database
  `ok`, and no poster-fetch errors or API tracebacks appeared in the checked logs.
- Actual production API-container DoH lookup and poster downloads succeeded for
  movie/series catalogues and both new-release lists. Image responses were 200
  WebP; repeated uncached-browser HTTP requests took 5–6 ms through disk cache
  (versus 132–537 ms for the initial tested downloads). The checked persistent
  cache contained 23 images totalling 1,075,840 bytes.
- Firefox on the Mac showed DNS mode `Защита по умолчанию` without any settings
  change. New releases, movie catalogue/details and series catalogue displayed
  posters. DevTools showed requests only to KADR `/api/v1/posters/...`; a repeat
  reload marked the image responses `кешировано`, with zero-ms cache timings.

## Known issues and next actions

The physical Android 11 television is not connected through ADB. Verify its
catalogue and movie/series details on the physical device. Updated API links
already work with the existing APK; legacy persisted absolute links also need
the new client helper. The emulator booted and accepted the clean-commit APK,
but visual TV acceptance remains unverified: the native emulator window was
not exposed by the UI tool, and opening Android Studio stalled and ended with
an expired-tool-continuation error. No physical TV success is claimed. One API worker
per cache directory is supported. Cached images remain usable during an outage
until their TTL; uncached failures render the web placeholder. An upstream
outage is tested with isolated test doubles, without changing production DNS.

## Post-deployment follow-up — 2026-11-19

All five services remained healthy on the follow-up check; API health returned
`status=ok` and `database=ok`. From the Mac, movie 1263337 and series 1413 details
returned KADR-relative poster and backdrop links. All four image requests
returned HTTP 200 WebP (85,328 / 95,316 and 49,366 / 111,398 bytes respectively).
No browser, Keenetic, or system DNS configuration was changed. The diagnostic
Google TV emulator was closed after checking the isolated build.
