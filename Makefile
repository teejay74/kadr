.PHONY: up down logs test test-backend test-frontend lint compose-check

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs --tail=200

test: test-backend test-frontend

test-backend:
	docker compose run --rm --no-deps api-test pytest -p no:cacheprovider

test-frontend:
	docker compose run --rm --no-deps web-test npm test -- --run

lint:
	docker compose run --rm --no-deps api-test ruff check --no-cache app tests
	docker compose run --rm --no-deps web-test npm run type-check

compose-check:
	docker compose config --quiet

