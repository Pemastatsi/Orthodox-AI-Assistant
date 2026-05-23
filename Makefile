.PHONY: dev test safety lint typecheck migrate up down install

install:
	(cd backend && uv sync)
	(cd web && pnpm install)

dev:
	docker compose -f infrastructure/docker-compose.yml up -d
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) &
	(cd web && pnpm dev)

test:
	(cd backend && uv run pytest -q)
	(cd web && pnpm test --run)

safety:
	pytest tests/safety -v

lint:
	(cd backend && uv run ruff check . && uv run mypy app)
	(cd web && pnpm lint && pnpm typecheck)

typecheck: lint

migrate:
	(cd backend && uv run alembic upgrade head)

up:
	docker compose -f infrastructure/docker-compose.yml up -d

down:
	docker compose -f infrastructure/docker-compose.yml down
