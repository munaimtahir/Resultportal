.PHONY: dev migrate superuser run collect import-students import-results install fmt lint test analytics

install:
	pip install -r requirements.txt

dev:
	python -m venv venv && . venv/bin/activate && pip install -r requirements.txt || true

migrate:
	cd server && python manage.py migrate

superuser:
	cd server && python manage.py createsuperuser

run:
	cd server && python manage.py runserver 0.0.0.0:8000

collect:
	cd server && python manage.py collectstatic --noinput

import-students:
	cd server && python manage.py import_students ../students.csv

import-results:
	cd server && python manage.py import_results ../results.csv

fmt:
	black server/
	ruff check --fix server/

lint:
	ruff check server/
	black --check server/

test:
	cd server && pytest --cov=apps --cov-report=term-missing

analytics:
	cd server && python manage.py compute_analytics
