# Episode Matcher usability fix report

Date: 2026-11-09

## Completed work

- Explained in the dialog that episode matching connects each video file to the
  episode KADR should open.
- Replaced the disabled dead end with an active `Продолжить` action when all
  available matches are already saved or no file has a selectable candidate.
- Changed the manual action to `Сохранить и продолжить` so its effect is clear.
- Kept files that need a decision prominent and moved automatically confirmed
  files into a compact expandable summary.
- Continued the source workflow after the dialog for episode playback, season
  download, and source-only selection.
- Made the backend `requires_confirmation` flag describe only safe files with
  selectable episode candidates.

## Changed files

- `backend/app/services/episodes/matcher.py`
- `backend/tests/test_episode_matcher.py`
- `frontend/src/components/EpisodeMatchDialog.vue`
- `frontend/src/components/EpisodeMatchDialog.test.ts`
- `frontend/src/components/SourcesPanel.vue`
- `frontend/src/components/SourcesPanel.test.ts`
- `frontend/src/pages/MediaDetailsPage.vue`
- `frontend/src/styles/main.css`
- `docs/api.md`
- This report

## Checks and test results

- Full backend Pytest suite: `151 passed`.
- Full frontend Vitest suite: `88 passed` across 14 files.
- Targeted dialog, source-panel, and media-details frontend tests: `26 passed`.
- Strict Vue TypeScript check and Vite production build: passed.
- Ruff: passed with cache disabled in the read-only test container.
- Docker Compose configuration: valid. No KADR runtime services were running,
  so there were no service health states or logs to inspect.

## Known issues

- A file with no reliable episode candidate remains unbound. The dialog now
  allows the workflow to continue, but KADR cannot infer an episode number that
  is absent from both the filename and catalogue evidence.
- Combined files still have no in-file timestamps, so exact navigation to the
  beginning of a later episode is unavailable.

## Next actions

- Rebuild and deploy the KADR API and web images through the existing deployment
  process; no running services were modified by this fix.
