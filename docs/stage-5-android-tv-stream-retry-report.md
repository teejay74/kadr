# Stage 5 follow-up — Android TV torrent stream recovery

## Completed work

- Set the Android TV torrent stream read timeout to 45 seconds so it can wait
  through the server's default 30-second piece timeout.
- Let Media3 retry temporary connection failures and HTTP 502, 503, and 504 up
  to four consecutive times. The player stays open and shows buffering when
  playback is waiting. After retries are exhausted, OK retries in the player.
- A missing source, invalid range, or unsupported format fails without the
  torrent retry delays. Saved library streams use the usual Media3 policy.

## Changed files

- Android player: `PlayerScreen.kt` and `TorrentLoadErrorPolicy.kt` in
  `android-tv/app/src/main/java/ru/kadr/tv/ui/`.
- Regression tests: `TorrentLoadErrorPolicyTest.java` in
  `android-tv/app/src/test/java/ru/kadr/tv/ui/`.
- User and streaming documentation: `docs/android-tv.md` and `docs/streaming.md`.

## Checks and results

- All 28 Android unit tests passed, and Gradle produced the debug APK.
- On the Google TV emulator, the isolated HTTP fixture passed its health check,
  returned HTTP 504 after 12 seconds on the first video request, and served the
  range with HTTP 206 after a further 10-second delay on the second request.
  The app showed buffering, retried after 2 seconds without user input, and
  reported a playback position of 5 seconds. The player and crash logs had no errors.
- The original emulator server address was restored after the check.

## Known issues and next actions

The reproduction used a controlled HTTP fixture. Install the updated APK on
the physical TV and recheck the affected torrent there.
