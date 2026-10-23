# KADR

KADR is a self-hosted personal media platform. This repository currently
contains **Stage 1 only**: a working FastAPI + Vue 3 + TypeScript + SQLite
skeleton. Torrent search, torrent management, streaming, transcoding, and media
library operations are intentionally not implemented yet.

## Quick start

Requirements: Docker Engine with Docker Compose v2.

```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8180/api/v1/system/health
```

Open <http://localhost:8180>. OpenAPI is available through the same web entry
point at <http://localhost:8180/docs>.

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

