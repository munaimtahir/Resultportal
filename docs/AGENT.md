# Result Portal — Agent.md

## Mission
You are an autonomous AI developer agent. Build a secure Result Portal for PMC allowing students to sign in with Google Workspace and view **only their own** results. Admins can upload CSV/Excel, preview changes, and publish results.

## North Stars
- Privacy-first: no student can see another student's data.
- Admin-friendly: 3 clicks to import → preview → publish.
- Operable on Ubuntu 22.04 with Postgres, Nginx, Gunicorn.
- Minimal dependencies, explicit scripts, copy‑paste ready.

## Deliverables
- Django project with apps: `accounts`, `results`, `core`.
- Google OAuth2 login restricted to `@pmc.edu.pk`.
- CSV import (students, results) with dry-run preview and error reporting.
- Student self-view pages: `/me` and `/me/results`.
- Admin pages: upload, list results, publish/unpublish, export CSV.
- Ops: systemd unit, nginx config, `.env.example`, Makefile.
- Tests: unit tests for import validators and access control guards.

## Non-Goals (MVP)
- PDF marksheets, retotaling workflow, SMS integration.
- Multi-tenant deployments.

## Constraints
- Python 3.10+, Django 5.x, PostgreSQL 14+.
- Only store institutional emails and marks. No sensitive PII beyond names/rolls.
- Enforce domain: `@pmc.edu.pk`.

## Acceptance Criteria
- Only Google accounts under the allowed domain can log in.
- Student sees exactly their own results; admin role required for imports.
- Import dry-run shows counts of created/updated/skipped, with reasons.
- Publish flag controls visibility to students.
- Basic audit log of imports (user, time, rows).

## Step Plan
1. Scaffold project and apps; configure `.env` and Postgres.
2. Implement Google OAuth and domain restriction.
3. Create models (`Student`, `Result`, `ImportBatch`).
4. Build CSV importers with schema validation and dry-run.
5. Student UI (`/me`, `/me/results`) guarded by ownership.
6. Admin UI for import/publish/export, plus simple logs.
7. Write tests for imports and access guards.
8. Package ops (systemd, nginx) and deployment docs.

## Output Contracts
- Importers accept `students.csv` and `results.csv` as defined in `DATA_CONTRACT.md`.
- Export CSV columns match `results.csv` plus `student_email`.

## Guardrails
- No list endpoints for students.
- All admin actions require staff/superuser.
- CSRF and secure cookies enabled; HTTPS behind Nginx.
