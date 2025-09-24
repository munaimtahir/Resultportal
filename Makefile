.PHONY: dev migrate superuser run collect import-students import-results

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
