# Result Portal — Starter (Plain‑Language Blueprint + File Templates)

This starter pack includes:
- Plain-language blueprint (README)
- Data templates for **students** and **results** CSV imports
- Email template (Markdown) for personalized result announcements
- `.env.example` for environment variables
- Suggested Django app structure (folders only; you will initialize Django later)

For the technical multi-stage prompt, see your ChatGPT message (copy it into `TECH_PROMPT.md` if you like).

## Stage 1 — Google Workspace Authentication

- Google OAuth2 login wired via `social-auth-app-django` with domain restriction to `@pmc.edu.pk` accounts.
- Custom pipeline links authenticated users to `Student` records (created from roster imports).
- Minimal UI for `/accounts/login/` providing a Google sign-in button and messaging for restricted access.
- Staff accounts signing in with the institutional domain are auto-provisioned to simplify admin onboarding.

## Stage 2 — Core Data Model Foundations

- Expanded the `Student` roster schema to capture roll numbers, display names, cohort metadata, and activity status flags while preserving Google linkage.
- Added an `ImportBatch` audit log model to record each roster/results CSV ingestion, including row counts and operator context.
- Introduced a normalized `Result` model with validation guards to ensure marks integrity and tie each record back to the responsible import batch.

## Stage 3 — CSV Import Workflows

- Implemented student and result CSV importers that validate schema compliance, enforce domain/marks rules, and support dry-run previews before committing changes.
- Each import generates an `ImportBatch` summary capturing created/updated/skipped counts alongside row-level diagnostics to assist operators in resolving issues.
- Added test coverage to guarantee that dry-run previews leave the database untouched while committed runs create/update the expected records.
