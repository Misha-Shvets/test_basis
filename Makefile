.PHONY: build up down build_test test migrate migration

build:
	docker compose build

up:
	docker compose up

build_test:
	docker compose -f docker-compose.test.yml build

down:
	docker compose down

test:
	docker compose -f docker-compose.test.yml run --rm test

migrate:
	docker compose run --rm --build migrations alembic upgrade head

migration:
	@test -n "$(message)" || (echo "Usage: make migration message=\"description\""; exit 1)
	docker compose run --rm --build -v "$(PWD)/app/infra/db/alembic:/app/infra/db/alembic" migrations alembic revision --autogenerate -m "$(message)"
