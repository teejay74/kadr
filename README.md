# KADR

KADR is a self-hosted personal media platform. The repository currently
contains the **Stage 6 media-library increment**: a working FastAPI + Vue 3 + TypeScript
application with a TMDB catalogue, isolated Prowlarr source search,
server-side qBittorrent control, availability-aware HTTP byte ranges, and a
Direct Play browser player. An explicit “Совместимая версия” action uses
`ffprobe` and FFmpeg to remux or transcode completed files to browser-friendly
H.264/AAC MP4. Fully downloaded selections can be saved to an isolated local
library, replayed without a torrent source, favorited, resumed across browsers,
and explicitly deleted with protected path checks.

UI redesign substages B1-C1 add normalized season/episode metadata, a shared
film/series presentation layer, episode-aware persistence, and a unified
backend playback resolver. Series pages show an adaptive episode list directly
below the hero and remember the last selected season in the browser. One
torrent task can retain several episode-to-file bindings, including multiple
file variants for one logical episode. Library items and watch history are
independent per episode and profile key. Film and episode play actions now ask
the backend to prefer a playable library copy, reuse a persisted torrent-file
binding, restore resume state, and report a controlled ready, buffering,
source-required, or unavailable state. The legacy source panel remains as the
manual fallback until the replacement selector passes end-to-end checks.
The server-side Episode Matcher recognizes common English and Russian episode
markers, validates them against TMDB, saves only unique exact matches
automatically, and opens a confirmation dialog for probable or ambiguous
files. Saved mappings are reused by torrent identity and file ID after restart.
UI redesign C2 opens a normalized source-selection modal only when a source is
missing, unavailable, or explicitly replaced. Raw release names stay inside
technical details; series selections pass through Episode Matcher, while a new
film release gets its preferred safe video selected by the backend.
UI redesign D1 adds backend-owned next-episode navigation across season
boundaries. Near the end of a torrent episode KADR may prefetch exactly one
confirmed next file from the same release; completion opens a configurable
next-episode overlay. Combined files are never presented as having an exact
episode seek point unless future stored time boundaries make that possible.
The final D2 UI increment moves torrent progress, pause/resume controls, file
inspection, and completed-cache deletion to a dedicated **Downloads** page.
Film and series pages retain only playback, source choice, and a link to that
technical workspace. The legacy `SourcesPanel` source remains in the tree for
live-playback rollback until Debian acceptance is complete.
Playback stabilization D2.1 reports selected-file progress during readiness
polling and lets MKV/WebM sources start from their initial pieces without
waiting for unrelated trailing data. MP4/MOV and AVI keep their bounded tail
probe.
Audio/subtitle stage D3.1 adds on-demand, bounded `ffprobe` discovery for a
completed selected torrent file or one saved library item. It returns stable
semantic preference keys plus exact stream IDs, languages, codecs, labels,
defaults, and delivery capabilities without starting FFmpeg or scanning a
season in the background.

## Quick start

Requirements: Docker Engine with Docker Compose v2.

```bash
cp .env.example .env
# Add a TMDB API Read Access Token to KADR_TMDB_ACCESS_TOKEN in .env.
docker compose up -d prowlarr
# Configure an authorized torrent indexer at http://127.0.0.1:9696,
# then copy Prowlarr's API key into KADR_PROWLARR_API_KEY in .env.
docker compose up -d qbittorrent
# Set a private Web UI account at http://127.0.0.1:8081 and copy the same
# username/password into the KADR_QBITTORRENT_* variables.
docker compose up --build -d
curl http://localhost:8180/api/v1/system/health
```

Open <http://localhost:8180>. OpenAPI is available through the same web entry
point at <http://localhost:8180/docs>.

TMDB credentials stay in the backend container. Without a token, system health
remains available while catalogue endpoints return a controlled `503` response
and the UI explains that metadata is not configured.

Prowlarr's setup UI is bound to loopback only; it is not exposed to the LAN.
KADR ships with no indexer credentials or preconfigured trackers. Follow the
[Prowlarr setup guide](docs/prowlarr.md) and use only sources whose rules permit
your access. The internal FlareSolverr service can handle supported Cloudflare
browser challenges for explicitly tagged indexers; it is not published on a
host port and cannot overcome a hard IP block.

qBittorrent's administration port is also loopback-only. New magnets stop as
soon as metadata arrives. Choose a film or episode with the single
«Выбрать и скачать» action; KADR selects only that file and starts it. KADR
searches every known series season separately and shows the season groups
collapsed by default. Multi-season packs such as `S01-05` are deduplicated and
shown in their own range group; «Скачать сезон» lets the viewer choose one
season from the pack. The action selects its first episode for playback and
queues the remaining episodes. The same action is
available later without changing the episode being watched. Then use «Начать
просмотр» for Direct Play.
If video works but audio does not, wait for the file to finish and choose
«Быстро исправить звук» to copy the video and convert only the first audio
track. Use «Полная совместимая версия» when the video codec is unsupported;
FFmpeg never starts automatically.
See the [qBittorrent setup guide](docs/qbittorrent.md) and
[streaming guide](docs/streaming.md).

After a selected video reaches 100%, use «Сохранить в библиотеку». The
«Библиотека» page reports saved size, plays the independent copy, and requires
confirmation before deletion. Temporary stopped downloads older than the
configured TTL are eligible for cache cleanup; saved and active media are
protected.

Stop KADR without deleting its database:

```bash
docker compose down
```

Do not add `-v`: removing persistent data is intentionally a separate,
destructive operation.

## Checks

```bash
docker compose config --quiet
docker compose build
docker compose run --rm --no-deps api-test pytest -p no:cacheprovider
docker compose run --rm --no-deps api-test ruff check --no-cache app tests
docker compose run --rm --no-deps web-test npm test -- --run
docker compose run --rm --no-deps web-test npm run type-check
```

The SQLite file is stored in `data/database/` outside the API container. Review
permissions, port availability, and `.env` before deploying to Debian.

## Documentation

- [Architecture](docs/architecture.md)
- [Deployment](docs/deployment.md)
- [API](docs/api.md)
- [Storage](docs/storage.md)
- [Streaming scope](docs/streaming.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Stage 1 report](docs/stage-1-report.md)
- [Stage 2 report](docs/stage-2-report.md)
- [Prowlarr setup](docs/prowlarr.md)
- [Stage 3 report](docs/stage-3-report.md)
- [qBittorrent setup](docs/qbittorrent.md)
- [Stage 4 report](docs/stage-4-report.md)
- [Stage 5 report](docs/stage-5-report.md)
- [Stage 5 compatibility report](docs/stage-5-compatibility-report.md)
- [Stage 6 report](docs/stage-6-report.md)
- [UI redesign B1 report](docs/ui-redesign-b1-report.md)
- [UI redesign B2 report](docs/ui-redesign-b2-report.md)
- [UI redesign C1 report](docs/ui-redesign-c1-report.md)
- [Episode Matcher report](docs/ui-redesign-episode-matcher-report.md)
- [UI redesign C2 report](docs/ui-redesign-c2-report.md)
- [UI redesign D1 report](docs/ui-redesign-d1-report.md)
- [UI redesign D2 report](docs/ui-redesign-d2-report.md)
- [UI redesign D2.1 report](docs/ui-redesign-d2-1-report.md)
- [Audio/subtitle D3.1 report](docs/ui-redesign-d3-1-report.md)
- [FlareSolverr deployment report](docs/stage-6-flaresolverr-report.md)

