# Streaming

Stage 5 uses Direct Play first for the video selected through Torrent Manager.
For unsupported containers or codecs, the user can explicitly request a
browser-compatible MP4. KADR then probes the completed source with `ffprobe`
and starts one bounded FFmpeg preparation job. FFmpeg is never started by
opening the player or by background automation.

## Request flow

1. The user explicitly opens the native HTML5 player.
2. The frontend polls `GET /api/v1/torrents/{task_id}/stream/readiness` every
   five seconds while the startup pieces are unavailable. This also starts or
   resumes the selected download.
3. Once the beginning and container tail are ready, the browser requests
   `GET /api/v1/torrents/{task_id}/stream`, usually with a byte range.
4. KADR validates the range and canonical selected-file path.
5. KADR maps that file range to torrent piece numbers and queries
   qBittorrent's piece states.
6. If the selected torrent is incomplete, KADR enables sequential download,
   prioritizes its first/last pieces, and starts it subject to the Torrent
   Manager's storage and concurrency gates.
7. KADR waits for the initial buffer, returns `200` or `206`, and checks piece
   availability again before every chunk read.
8. Completion, closing the player, navigation, or a disconnected client
   releases the active-stream slot.

KADR never treats file length or sparse bytes as proof that data is ready. A
piece is readable only when qBittorrent reports state `2` (downloaded).

## Range behavior

Single explicit (`bytes=10-99`), open (`bytes=10-`), and suffix (`bytes=-90`)
ranges are supported. Multiple ranges are rejected with `416`; multipart range
responses are not part of the MVP. Seek requests create independent bounded
stream sessions and work in both directions when the requested pieces become
available before timeout.

The qBittorrent Web API exposes sequential mode, first/last-piece priority,
piece state, and file priority, but no arbitrary piece-priority operation. KADR
enables the available streaming hints and reasserts normal priority for the
selected file. Maximal priority is intentionally avoided because qBittorrent
5.x can then keep a rarest-first queue instead of fetching the beginning of the
video. KADR still cannot force a distant seek range ahead of other pieces, so
such a seek can time out cleanly on an incomplete torrent.

## Buffer and limits

| Variable | Default | Meaning |
| --- | ---: | --- |
| `KADR_MAX_ACTIVE_STREAMS` | `2` | Concurrent distinct torrent-task limit |
| `KADR_MAX_RANGE_REQUESTS_PER_STREAM` | `32` | Parallel HTTP ranges allowed per task |
| `KADR_STREAM_START_BUFFER_MB` | `32` | Initial adaptive buffer cap |
| `KADR_STREAM_READ_TIMEOUT_SECONDS` | `30` | Maximum wait for a needed piece/file |
| `KADR_STREAM_POLL_INTERVAL_SECONDS` | `0.5` | Piece-state refresh interval |
| `KADR_STREAM_CHUNK_SIZE_KB` | `1024` | Read and response chunk size |

The initial target starts at one response chunk, grows to roughly four seconds
of current download speed, and is capped by the configured value and requested
range length. This is a startup heuristic, not a guarantee of uninterrupted
playback. Every emitted chunk is still gated by its actual torrent pieces.

Browsers commonly open several parallel or replacement Range requests for one
native video element. Requests for the same torrent task share one active
stream slot, while the per-task Range limit keeps concurrency bounded.

## Player behavior

The browser supplies play, pause, volume, mute, progress, seeking, fullscreen,
and any supported embedded track controls. KADR stores the last meaningful
position in that browser's local storage and offers to continue on the next
opening. Before attaching the media source, the player displays real startup
buffer readiness and waits automatically instead of turning a preparation
timeout into a browser format error. The visible player frame reports the
selected-file download percentage, torrent state, speed, buffer progress, and
five-second retry behavior. Once ready, KADR attempts playback and reports an
explicit browser autoplay block instead of leaving an empty player area.
Closing the player cancels readiness polling and removes its media source.
KADR sends explicit video MIME types even
when the minimal container image lacks a system MIME database. Container and
codec support still depends on the browser/TV; an unsupported file produces a
codec-specific player error. The retry action creates a fresh media request,
and “Change source” returns to the release list without deleting the existing
KADR download.

## Compatible playback

“Совместимая версия” is an explicit alternative to Direct Play. The selected
file must be completely downloaded first. KADR chooses the least expensive
safe strategy after probing the actual streams:

| Source streams | Preparation |
| --- | --- |
| H.264 8-bit 4:2:0 + AAC-LC (or no audio) | Remux to MP4; copy streams |
| H.264 8-bit 4:2:0 + other audio | Copy video; convert first audio track to AAC-LC stereo |
| Other video (HEVC, AV1, 10-bit, etc.) | Convert video to H.264 8-bit and first audio track to AAC-LC stereo |

The result is written atomically as
`data/playback/{task_id}/compatible.mp4`; the download mount remains read-only
inside the API. Once ready, the file supports the same single byte-range
contract as Direct Play. Reopening it reuses the cached result.

Full video conversion is CPU-intensive and completes before playback begins.
The default is one concurrent preparation, two video threads, CRF 23,
`veryfast`, and at most 1920×1080. Embedded subtitles and alternate audio
tracks are not yet exposed, HDR is not tone-mapped, and compatibility cannot
be guaranteed for every browser/device.

| Variable | Default | Meaning |
| --- | ---: | --- |
| `KADR_PLAYBACK_CACHE_ROOT` | `/playback` | Separate compatible-file output root |
| `KADR_PLAYBACK_MIN_FREE_SPACE_GB` | `5` | Free space retained after estimated output |
| `KADR_MAX_ACTIVE_TRANSCODES` | `1` | Concurrent FFmpeg preparations |
| `KADR_TRANSCODE_VIDEO_THREADS` | `2` | FFmpeg video encoder threads |
| `KADR_TRANSCODE_VIDEO_PRESET` | `veryfast` | H.264 encoder speed/efficiency trade-off |
| `KADR_TRANSCODE_VIDEO_CRF` | `23` | H.264 quality factor |
| `KADR_TRANSCODE_MAX_WIDTH/HEIGHT` | `1920` / `1080` | Maximum output dimensions |
| `KADR_TRANSCODE_AUDIO_BITRATE` | `192k` | AAC output bitrate |

