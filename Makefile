.PHONY: install run lint format typecheck test test-unit test-integration architecture migrate docker-up docker-down build

install:
	uv sync --frozen

run:
	uv run uvicorn valor.main:create_app --factory --reload

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration

architecture:
	uv run pytest tests/architecture

migrate:
	uv run alembic upgrade head

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

build:
	uv build

