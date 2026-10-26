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
collapsed by default. «Скачать сезон» on a seasonal release selects its first
episode for playback and queues the remaining episodes. The same action is
available later without changing the episode being watched. Then use «Начать
просмотр» for Direct Play.
If its container or codecs are unsupported, wait for the file to finish and
choose «Совместимая версия»; FFmpeg never starts automatically.
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
- [FlareSolverr deployment report](docs/stage-6-flaresolverr-report.md)

