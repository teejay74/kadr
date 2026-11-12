# Stage 7 report — catalogue availability during TMDB outages

Date: 2026-11-12

## Completed work

- Reproduced the failure on the live API: health and a cached film returned
  `200`; an uncached film and the new-release query returned
  `502 metadata_unavailable`.
- Detail endpoints can return the saved catalogue entry for the exact media
  type and ID when full details fail. The web shows a notice and a retry button.
- Date-window discovery can serve yesterday's matching page during an outage.
  The home page renders successful collections even when another fails.

## Changed files

- Backend catalogue routes, service, cache repository, response schema, and
  catalogue tests.
- Web home and detail pages, media types, and the home page regression test.
- API and troubleshooting documentation.

## Checks and test results

- Full backend suite: 159 passed, including health and simulated provider
  outages. Ruff passed.
- Web production build and type checking passed. Full web suite: 99 passed.
- No production or network settings were changed.

## Known issues and next actions

- Deploy the application changes and verify the affected card and home page.
- Verify DNS and VPN routing for `api.themoviedb.org` from the API container.
  A title without a matching cached entry still needs a reachable provider.
