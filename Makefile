# Makefile
.PHONY: up down build logs backend-shell db-shell migrate seed

up:
    docker compose up -d --build

down:
    docker compose down

logs:
    docker compose logs -f

backend-shell:
    docker compose exec backend /bin/sh

db-shell:
    docker compose exec db psql -U sms_admin -d sms_db

migrate:
    docker compose exec backend alembic upgrade head

seed:
    docker compose exec backend python -m app.db.seed