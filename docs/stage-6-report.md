# Stage 6 report — Media library

Date: 2026-10-25

## Completed

- Added migrated SQLite models for saved library items, favorites, and watch history.
- Added explicit save of a fully downloaded selected video with hard-link-first,
  safe-copy fallback, temporary output, and atomic rename.
- Added an isolated library mount and HTTP Range playback independent of the
  torrent source.
- Added protected deletion with canonical-root and active-stream checks.
- Added favorites and server-side playback resume/completion updates.
- Added a Library page with saved byte totals, playback, favorites, and
  confirmation before deletion.
- Added guarded manual and low-frequency TTL cache cleanup. Active downloads,
  active streams, and saved tasks are skipped.
- Added storage status for library/cache counts, bytes, and free space.

## Safety boundaries

- The API can write only its database, playback cache, and KADR library mount;
  torrent downloads remain read-only to it.
- No Photodom path is mounted, inspected, changed, or deleted.
- Library and download paths are canonicalized against configured KADR roots.
- Cache deletion targets only a known expired database task through the
  isolated qBittorrent instance after saved/active checks.

## Verification

- Backend Pytest: `52 passed`.
- Frontend Vitest: `20 passed` across 6 files.
- Ruff: passed; TypeScript check and production Vite build: passed.
- Alembic migrated the live local database from `0003` to `0004_library`.
- Compose configuration is valid; API, web, Prowlarr, and qBittorrent are healthy.
- Live `/system/health`, `/library`, `/favorites`, and `/system/storage`
  requests returned `200` through nginx.
- Live storage status reported 8 cache tasks and 4,593,544,425 downloaded
  bytes. Cleanup was deliberately not invoked during acceptance, so existing
  media was not removed.

## Known limitations

- The current local profile is single-user; role-based accounts are required
  before untrusted or public access.
- Saving a season currently stores the selected episode as the media entry;
  episode-aware grouping needs richer season/episode identity.
- Compatible FFmpeg artifacts retain their separate playback-cache lifecycle.

## Next action

Stage 7 adds directional TV focus, remote-control interaction, player
adaptation, and a measured Android TV / Google TV compatibility matrix.
