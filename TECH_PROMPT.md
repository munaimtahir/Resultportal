# Technical Multi-Stage Prompt

Use this as the canonical instruction for code generation and iteration. Follow stages strictly and keep code idempotent.

## Stage 0 — Bootstrap
- Create Django project `config` in `server/` and apps `accounts`, `results`, `core`.
- Settings from `.env` (see `.env.example`).
- Install deps: `django`, `psycopg2-binary`, `social-auth-app-django`, `python-dotenv`, `gunicorn`.
- Postgres connection via env vars; timezone `Asia/Karachi`.

## Stage 1 — Google OAuth (Workspace)
- Integrate `social-auth-app-django`.
- Restrict login to emails ending with `@pmc.edu.pk`.
- On login, create/link Django User; map to `Student` via `official_email` (exact match).

## Stage 2 — Models
- `Student(roll_no unique, display_name, first_name, last_name, official_email unique, batch_code, status)`
- `ImportBatch(uploaded_by, uploaded_at, file_name, row_count, subject, block, year, notes)`
- `Result(student FK, block, year, subject, written_marks, viva_marks, total_marks, grade, exam_date, import_batch FK, visibility)`

## Stage 3 — Importers
- CSV parsers in `core/importers.py` with dataclass schemas.
- Dry-run returns a structured report: `created`, `updated`, `skipped` with reasons.
- Commit path writes rows + ImportBatch log.
- Keys: `roll_no` for linking; fallback email (optional, off by default).

## Stage 4 — Views & Access
- Student views: `/me`, `/me/results` (login required).
- Admin views: upload CSV, list results w/ filters, publish toggle, export CSV.
- Decorators: `@login_required`, `@staff_member_required`; ownership checks for students.

## Stage 5 — Tests
- Test import validation (bad headers, type errors, missing students).
- Test ownership guards and domain restriction.

## Stage 6 — Ops
- Gunicorn systemd unit, Nginx site file, collectstatic.
- Makefile with `make dev`, `make migrate`, `make superuser`, `make run`, `make collect`, `make import-students`, `make import-results`.
- Simple backup script for Postgres.

Adhere to `DATA_CONTRACT.md` exactly.
