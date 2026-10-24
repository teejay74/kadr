# KADR

KADR is a self-hosted personal media platform. The repository currently
contains the **Stage 3 source-search implementation**: a working FastAPI + Vue
3 + TypeScript application with a TMDB catalogue and an isolated Prowlarr
integration that normalizes torrent-indexer results. Torrent downloading,
management, streaming, transcoding, and media-library operations are
intentionally not implemented.

## Quick start

Requirements: Docker Engine with Docker Compose v2.

```bash
cp .env.example .env
# Add a TMDB API Read Access Token to KADR_TMDB_ACCESS_TOKEN in .env.
docker compose up -d prowlarr
# Configure an authorized torrent indexer at http://127.0.0.1:9696,
# then copy Prowlarr's API key into KADR_PROWLARR_API_KEY in .env.
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
your access.

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

