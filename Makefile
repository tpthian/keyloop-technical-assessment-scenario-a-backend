.PHONY: install up down run test lint migrate demo spike

install:
	uv sync
	uv run pre-commit install

up:
	docker compose up -d --wait db

down:
	docker compose down

run:
	uv run uvicorn scheduler.main:create_app --factory --reload --port 8000

# testcontainers mounts this socket into its reaper container; colima and Docker Desktop
# expose a different host socket, so the in-VM path is given explicitly. Override if needed.
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE ?= /var/run/docker.sock

test:
	TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=$(TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE) uv run pytest -q

lint:
	uv run pre-commit run --all-files

demo:
	docker compose up -d --build --wait db api
	scripts/demo.sh

migrate:
	uv run alembic upgrade head

# Design-phase spikes (docs/evidence/spike/). They drop and recreate their own
# tables, so they run in a separate "spike" database on the compose server,
# never in the application database.
SPIKE_DATABASE_URL ?= postgresql://scheduler:scheduler@localhost:5432/spike

spike: up
	docker compose exec -T db sh -c 'createdb -U scheduler spike 2>/dev/null || true'
	DATABASE_URL=$(SPIKE_DATABASE_URL) uv run python -I docs/evidence/spike/race.py
	DATABASE_URL=$(SPIKE_DATABASE_URL) uv run python -I docs/evidence/spike/race_savepoint.py 8
