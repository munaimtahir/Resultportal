.PHONY: install fmt lint test migrate superuser run collect import-students import-results clean help

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies in virtual environment
	python -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip setuptools wheel
	. .venv/bin/activate && pip install -r requirements.txt

fmt:  ## Format code with black and isort
	. .venv/bin/activate && black server/
	. .venv/bin/activate && isort server/

lint:  ## Run linters (ruff, black check, isort check)
	. .venv/bin/activate && ruff check server/
	. .venv/bin/activate && black --check server/
	. .venv/bin/activate && isort --check-only server/

test:  ## Run tests with coverage
	. .venv/bin/activate && pytest

test-fast:  ## Run tests without coverage
	. .venv/bin/activate && pytest --no-cov

migrate:  ## Run Django migrations
	. .venv/bin/activate && cd server && python manage.py migrate

makemigrations:  ## Create new migrations
	. .venv/bin/activate && cd server && python manage.py makemigrations

superuser:  ## Create Django superuser
	. .venv/bin/activate && cd server && python manage.py createsuperuser

run:  ## Run development server
	. .venv/bin/activate && cd server && python manage.py runserver 0.0.0.0:8000

collect:  ## Collect static files
	. .venv/bin/activate && cd server && python manage.py collectstatic --noinput

import-students:  ## Import students from CSV (use FILE=path/to/file.csv)
	. .venv/bin/activate && cd server && python manage.py import_students $(FILE) --commit

import-students-dry-run:  ## Preview student import (use FILE=path/to/file.csv)
	. .venv/bin/activate && cd server && python manage.py import_students $(FILE) --dry-run

import-results:  ## Import results from CSV (use FILE=path/to/file.csv)
	. .venv/bin/activate && cd server && python manage.py import_results $(FILE) --commit

import-results-dry-run:  ## Preview results import (use FILE=path/to/file.csv)
	. .venv/bin/activate && cd server && python manage.py import_results $(FILE) --dry-run

clean:  ## Clean build artifacts and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache htmlcov .coverage
	rm -rf build dist *.egg-info

check:  ## Run Django system checks
	. .venv/bin/activate && cd server && python manage.py check

# === Docker Commands ===

docker-build:  ## Build Docker containers
	docker compose build

docker-up:  ## Start Docker containers in detached mode
	docker compose up -d

docker-down:  ## Stop Docker containers
	docker compose down

docker-logs:  ## View Docker container logs
	docker compose logs -f web

docker-shell:  ## Open shell in web container
	docker compose exec web bash

docker-migrate:  ## Run migrations in Docker
	docker compose exec web python manage.py migrate

docker-superuser:  ## Create superuser in Docker
	docker compose exec web python manage.py createsuperuser

docker-test:  ## Run tests in Docker
	docker compose exec web pytest

docker-clean:  ## Stop containers and remove volumes
	docker compose down -v

docker-restart:  ## Restart Docker containers
	docker compose restart
