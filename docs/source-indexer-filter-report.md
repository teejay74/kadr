# Source indexer filter report

Date: 2026-11-09

## Completed work

- Added a dynamic `Где искать` selector with `Во всех источниках` as the
  default and one option for every enabled torrent indexer configured in
  Prowlarr.
- Added the selector to both the unified source modal and the retained legacy
  source panel.
- Added an optional validated `indexer_id` to source search and torrent-add
  requests.
- Forwarded a selected indexer to Prowlarr's `indexerIds` search parameter, so
  other configured sites are not queried.
- Kept the selected indexer during opaque source resolution before adding the
  torrent to qBittorrent.
- Added a bounded season-search cascade: `S02`, localized `Сезон 2`, then the
  title alone, followed by the same variants for the original title when
  necessary.
- Removed the series premiere year from season queries because later seasons
  can be released in a different year.
- Filtered every cascade response by explicit parsed season coverage and added
  support for RuTracker-style `Сезон: 2` titles.
- Continued to expose only safe indexer summaries; API keys, tracker settings,
  download URLs, and magnet links remain server-side.

## Changed files

- `backend/app/api/v1/sources.py`
- `backend/app/api/v1/torrents.py`
- `backend/app/schemas/sources.py`
- `backend/app/schemas/torrents.py`
- `backend/app/services/sources/prowlarr.py`
- `backend/app/services/sources/release_parser.py`
- `backend/app/services/sources/search.py`
- `backend/app/services/torrents/manager.py`
- `backend/tests/test_sources.py`
- `frontend/src/components/SourceSelector.vue`
- `frontend/src/components/SourceSelector.test.ts`
- `frontend/src/components/SourcesPanel.vue`
- `frontend/src/components/SourcesPanel.test.ts`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/services/api.ts`
- `frontend/src/services/api.test.ts`
- `frontend/src/styles/main.css`
- `frontend/src/types/media.ts`
- `docs/api.md`
- `docs/architecture.md`
- This report

## Checks and test results

- Full backend Pytest suite: `154 passed`.
- Full frontend Vitest suite: `93 passed` across 14 files.
- Targeted source and torrent backend tests: `40 passed`.
- Targeted source-search tests after the cascade change: `24 passed`.
- Targeted API, selector, source-panel, and media-details frontend tests:
  `55 passed`.
- Fresh frontend test image production build, strict TypeScript, Ruff, and
  Docker Compose validation: passed.
- `docker compose ps` confirmed that no local KADR runtime services were
  running, so there were no service health states or runtime logs to inspect.
  No deployment or restart was performed.
- Read-only production diagnosis confirmed a healthy KADR API and RuTracker
  indexer ID 5. The old season-2 query ended at `MobLand 2025 S02` with zero
  results, while the same indexer returned eight releases without the season
  marker. This cascade follow-up has not been deployed, so live acceptance of
  the corrected RuTracker result remains a post-deployment check.

## Known issues

- The list contains only indexers already configured and enabled in Prowlarr;
  KADR does not configure tracker accounts.
- If Prowlarr cannot list indexers, source search remains available with the
  safe default of searching all configured indexers, but the filter is hidden.
- A provider can still return no results for a valid query because of its own
  category mapping, rate limit, availability, or search capabilities.
- Releases that do not identify a season anywhere in their title are excluded
  from season-specific results rather than guessed.

## Next actions

- After review, rebuild only the KADR API and web services and smoke-test one
  all-indexer search and one RuTracker-only or RuTor-only search on Debian.
