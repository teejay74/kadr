# Native Android TV stage A report — runnable client foundation

Date: 2026-10-28

## Native artwork stage — 2026-10-29

- Added Coil 3 Compose and its OkHttp network module for asynchronous artwork.
- Added cached posters to catalogue and search tiles, backdrops to details, and
  still images to episode rows.
- Retained branded local placeholders while images load or when artwork is
  absent/unavailable.
- Restricted artwork URLs to HTTPS or the configured KADR server origin;
  arbitrary public cleartext image hosts are rejected.
- Increased the APK to version `0.3.2` (`versionCode 7`).

## Native catalogue search stage — 2026-10-29

- Added a dedicated TV search screen reachable from the catalogue header.
- Added bounded text input with the system TV keyboard and a 600 ms debounce.
- Movie and series searches run concurrently through the existing versioned
  KADR API and render in separate D-pad rails.
- Opening a result preserves search query/results and Back returns to search.
- Added empty-result, retry, loading, cancellation, and server-error states.
- Increased the APK to version `0.3.1` (`versionCode 6`).

## Native series playback stage — 2026-10-29

- Added D-pad season and episode selection backed by real TMDB catalogue data.
- Added season-scoped Prowlarr source search and series torrent submission.
- Added bounded torrent metadata polling before episode analysis.
- Integrated the backend Episode Matcher. Exact safe matches are reused;
  ambiguous matches require an explicit file choice on TV before persistence.
- Added episode-aware playback resolution and the existing readiness/fullscreen
  Media3 flow for the selected episode.
- Added Back navigation across details, episodes, sources, matching,
  preparation, and player screens.
- Increased the APK to version `0.3.0` (`versionCode 5`).

## YaOS X playback/focus follow-up — 2026-10-29

- Added explicit D-pad Up/Down focus routes between the movie and series rails
  and initial focus on the first film, preventing the first Down press from
  moving horizontally.
- Replaced repeated full playback resolution during startup buffering with the
  dedicated stream-readiness endpoint. This avoids re-selecting the torrent
  file and resetting qBittorrent priorities on every poll.
- Buffer percentage shown on TV is now monotonic even when the backend adapts
  the required startup window to changing download speed. File progress and
  current speed are displayed separately.
- Startup waiting remains cancellable with Back and is bounded at ten minutes
  instead of returning to source selection after three minutes.
- Increased the APK to version `0.2.1` (`versionCode 4`).

## Playable-source follow-up — 2026-10-29

- Added native film-source search through the existing server-owned Prowlarr
  endpoint. Raw provider download URLs and credentials remain on the server.
- Added a D-pad-controlled source list showing resolution, source type, codec,
  language, size, and seeders, with a deterministic recommended option.
- Added source submission to the existing server-owned qBittorrent endpoint.
- Added bounded five-second playback polling for torrent metadata and startup
  buffering, followed by automatic fullscreen Media3 playback when ready.
- Back cancels local polling and returns to the source list; it does not delete
  the server-side torrent task.
- Increased the APK to version `0.2.0` (`versionCode 3`).

## YaOS X focus follow-up — 2026-10-29

- Reproduced the catalogue layout defect reported on a physical YaOS X TV:
  left/right focus worked inside a rail, but the non-scrollable parent could
  not reveal the next row.
- Replaced the catalogue `Column` with a keyed vertical `LazyColumn` and marked
  each horizontal rail as a focus group, so D-pad Up/Down moves between rows
  and scrolls the selected row into view.
- Increased the APK to version `0.1.1` (`versionCode 2`) for an in-place update.

## Completed work

- Added a standalone `android-tv` Gradle application using Kotlin, Compose for
  TV, and Media3 ExoPlayer.
- Declared a TV-only Leanback launcher, non-touch landscape activity, TV banner,
  and fullscreen system-bar behavior.
- Added persisted server configuration with a real KADR health request.
- Supported private LAN IP/hostnames, Tailscale `100.64.0.0/10` addresses,
  MagicDNS/`*.ts.net`, and HTTPS endpoints. Public cleartext HTTP is rejected.
- Added real movie/series catalogue rails and media details from the current
  versioned KADR API.
- Added backend-owned film playback resolution and conversion of relative
  stream paths to the configured server origin.
- Added fullscreen Media3 playback with server resume position.
- Added unit tests for LAN/Tailscale/HTTPS address validation, stream URL
  resolution, and source recommendation.

## Safety and architecture

- The APK contains no TMDB, indexer, qBittorrent, or server credentials.
- Torrent and filesystem operations remain exclusively in the backend.
- Cleartext is enabled at Android's transport layer because the user can enter
  a dynamic LAN/Tailscale IP; application validation limits HTTP to private or
  tailnet-style hosts. Public endpoints require HTTPS.
- No Photodom path, service, configuration, or network was accessed or changed.
- No existing KADR service was deployed or restarted.

## Verification

- `testDebugUnitTest`: passed (9 tests).
- `assembleDebug`: passed with Android SDK 36 and JDK 17.
- `lintDebug`: passed without errors. Remaining warnings report the deliberately
  pinned SDK/Compose toolchain and available future dependency updates.
- APK manifest inspected with `aapt`: package `ru.kadr.tv`, min SDK 24, target
  SDK 36, Leanback launcher present, touchscreen not required.
- The production LAN API was checked read-only after the reported buffering
  failure: the selected torrent remained active and its dedicated readiness
  endpoint progressed to `ready=true`; no KADR service was changed or restarted.
- The production LAN search API was checked read-only with the Cyrillic query
  `Дюна`: it returned 13 films and 3 series.
- A real TMDB `w500` poster URL returned by KADR was fetched successfully over
  HTTPS (`200 image/jpeg`); no image was copied into the APK.
- Debug APK produced at
  `android-tv/app/build/outputs/apk/debug/app-debug.apk` (15,914,590 bytes,
  SHA-256 `b14f68798dbd2c485a6c1703a9ae2fa83099fe3c1cc45b2df2549d3318690167`).
- Physical Android TV installation and remote/device codec acceptance remain
  pending.

## Known limitations

- Combined files containing multiple episodes can be associated with the
  selected episode, but native chapter/time-boundary navigation is not yet
  available.
- Native audio/subtitle selection, history writes, next episode, library,
  downloads, and explicit compatibility preparation remain future increments.
- This debug APK is development-signed and is not a Play Store release bundle.

## Next actions

1. Install the debug APK on the target television and record LAN/Tailscale,
   D-pad, Back, fullscreen, Range-seek, and codec results.
2. Add audio/subtitle selection, history updates, next episode, and a measured
   compatibility fallback flow. FFmpeg must remain explicit and opt-in.
