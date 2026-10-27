# UI redesign report — Episode Matcher

Date: 2026-10-27

## Completed work

- Added a server-side Episode Matcher that inspects every supported video's
  full relative torrent path, including season folders.
- Recognized `S01E02`, `1x02`, English and Russian season/episode labels,
  combined markers, and bounded ranges.
- Validated parsed identities against normalized TMDB season metadata and used
  episode-title similarity only as secondary, non-automatic evidence.
- Accepted duration already present in torrent metadata as an auxiliary signal
  without downloading or probing media solely for matching.
- Classified results as `exact`, `probable`, or `ambiguous`; persisted only
  unique, conflict-free exact matches automatically.
- Persisted confidence and automatic/manual confirmation provenance by the
  torrent task identity and qBittorrent `file_id`; saved mappings are reused
  after application restart.
- Supported several logical episodes per physical file and retained the
  existing many-to-many seam for several file variants per episode.
- Added a future `segment_index` field without implementing multipart video
  concatenation or false seek guarantees for combined episodes.
- Added a Vue confirmation dialog for probable and ambiguous candidates and
  integrated it into the retained legacy source panel.
- Rejected absolute, traversal, control-character, and Windows drive paths.
- Left Streaming Manager and Direct Play behavior unchanged.

## Changed files

Backend:

- `backend/app/api/dependencies.py`
- `backend/app/api/v1/torrents.py`
- `backend/app/models/episodes.py`
- `backend/app/repositories/episodes.py`
- `backend/app/schemas/episode_matcher.py`
- `backend/app/schemas/torrents.py`
- `backend/app/services/episodes/__init__.py`
- `backend/app/services/episodes/matcher.py`
- `backend/app/services/torrents/manager.py`
- `backend/migrations/versions/0006_episode_matcher.py`
- `backend/tests/test_episode_matcher.py`

Frontend:

- `frontend/src/components/EpisodeMatchDialog.vue`
- `frontend/src/components/EpisodeMatchDialog.test.ts`
- `frontend/src/components/SourcesPanel.vue`
- `frontend/src/components/SourcesPanel.test.ts`
- `frontend/src/services/api.ts`
- `frontend/src/services/api.test.ts`
- `frontend/src/styles/main.css`
- `frontend/src/types/media.ts`

Documentation:

- `README.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/storage.md`
- `docs/troubleshooting.md`
- This report.

## Checks and results

- Fresh backend test image and full Pytest suite: `110 passed`.
- Dedicated matcher tests cover standard, alternate, English, Russian,
  combined, ranged, title-only, conflicting, duration-mismatch, persisted,
  manually confirmed, API, and unsafe-path cases.
- A real SQLite test upgrades an existing `0005_episode_persistence` database
  to `0006_episode_matcher`, verifies preserved rows/defaults, and verifies the
  new check constraint.
- Ruff over backend application, migrations, and tests: passed.
- Fresh frontend image, strict Vue TypeScript check, and Vite production build:
  passed.
- Full frontend Vitest suite: `54 passed` across 10 files.
- Docker Compose configuration validation: passed.
- No production services, Debian configuration, Photodom, or user data were
  changed during this substage.

## Known limitations

- A combined video can map to several episodes, but exact in-file time
  boundaries are not known, so KADR does not promise a precise jump to the
  second episode.
- The model can represent multipart variants through separate physical files
  and a future segment index, but automatic concatenation is not implemented.
- Title-only matches always require confirmation, even at a high similarity
  score.
- Confirmation requires TMDB metadata to be available so an invalid episode
  identity cannot be persisted through the UI.
- Duration contributes only when the torrent adapter already exposes it;
  qBittorrent normally does not, and KADR does not download a file to obtain it.
- The confirmation UI currently lives inside the retained `SourcesPanel`; C2
  will place source selection in the unified modal workflow while keeping the
  legacy panel for regression checks.

## Readiness for the next substage

Episode Matcher is complete and locally verified. C2 can implement the unified
`SourceSelector` modal for missing, unavailable, and explicitly replaced
sources. It must reuse backend matching results for series files, add new tests,
and retain `SourcesPanel` until movie, series, and library playback pass
end-to-end acceptance checks.
