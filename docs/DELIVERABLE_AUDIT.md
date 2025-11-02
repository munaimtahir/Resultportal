# Result Portal Code Audit

## Build & Runtime Blockers

1. **`Student` model is missing the domain helpers required by tests and importers.**
   - The model does not expose a `Status` `TextChoices` enum or an `is_active` convenience property, yet both the test-suite and importer reference them (for example `Student.Status.ACTIVE` in the importer/tests).【F:server/apps/accounts/models.py†L17-L88】【F:server/apps/accounts/tests.py†L18-L33】【F:server/apps/accounts/importers.py†L92-L107】
   - There is no custom queryset/manager exposing `Student.objects.active()`, so the tests will crash immediately.【F:server/apps/accounts/models.py†L17-L88】【F:server/apps/accounts/tests.py†L18-L31】

2. **`StudentCSVImporter` remains abstract because `_get_import_type` is never implemented.**
   - The base class marks `_get_import_type` as abstract, but the student importer omits it, so instantiation raises `TypeError` and the CSV workflow cannot run.【F:server/apps/core/importers.py†L52-L58】【F:server/apps/accounts/importers.py†L18-L199】

3. **Student/Result CSV importer tests rely on fixtures that were never initialised.**
   - `ResultCSVImporterTests.setUp` lacks the body that should build staff users, students, and seed results, so every test fails before assertions run.【F:server/apps/results/tests.py†L92-L172】
   - Several result tests also reference `datetime`/`date` without importing them, so they error before setup completes.【F:server/apps/results/tests.py†L52-L172】

4. **Operational tooling points at missing management commands.**
   - The Makefile’s `import-students`/`import-results` targets call `manage.py import_students` and `import_results`, but no such commands exist, so the documented ops flow immediately fails.【F:Makefile†L1-L18】

## Feature Completion vs. Specification

| Feature | Status | Notes |
| --- | --- | --- |
| Google Workspace SSO w/ domain enforcement | **Partially implemented** | Pipeline enforces the domain, but Student model bugs block linking accounts and migrations.【F:server/apps/accounts/pipeline.py†L13-L71】【F:server/apps/accounts/models.py†L17-L88】 |
| Student roster import (dry-run + commit) | **Broken** | Importer cannot instantiate due to missing `_get_import_type`; Student model helpers missing for status normalisation.【F:server/apps/accounts/importers.py†L18-L199】 |
| Result import & publish tracking | **Partially implemented** | Importer logic exists, but its tests are incomplete/missing setup which hides regressions.【F:server/apps/results/importers.py†L1-L203】【F:server/apps/results/tests.py†L92-L172】 |
| Student self-service views (`/me`, `/me/results`) | **Not started** | No URLs or views reference these endpoints anywhere in the project.【F:server/config/urls.py†L17-L23】【F:server/apps/results/views.py†L1-L3】 |
| Admin import/publish UI | **Not started** | Admin only registers models; no custom views/templates for the three-click workflow exist.【F:server/apps/results/admin.py†L1-L33】【F:server/apps/accounts/admin.py†L1-L9】 |
| Audit logging of imports | **Partial** | `ImportBatch` model exists, but without CLI/commands the log is unreachable via ops tooling.【F:server/apps/results/models.py†L13-L75】【F:Makefile†L13-L18】 |
| Test coverage for import/access guards | **Red** | Tests reference missing helpers and incomplete fixtures, so the suite cannot run to validate behaviour.【F:server/apps/accounts/tests.py†L16-L200】【F:server/apps/results/tests.py†L92-L172】 |

## Mandatory Pre-Deployment TODOs

1. Restore the full `Student` domain model (queryset, manager, status enum, helper properties) so migrations/tests/importers align with the data contract.【F:server/apps/accounts/models.py†L17-L88】【F:server/apps/accounts/tests.py†L18-L33】
2. Implement `_get_import_type` in `StudentCSVImporter` and clean up unused imports so the importer can create `ImportBatch` records.【F:server/apps/accounts/importers.py†L18-L199】
3. Rebuild the student and result importer tests to seed fixtures correctly and import all required stdlib modules, ensuring we can trust the regression suite.【F:server/apps/accounts/tests.py†L130-L200】【F:server/apps/results/tests.py†L92-L172】
4. Provide `import_students`/`import_results` management commands that wrap the CSV importer APIs, matching the Makefile and deployment docs.【F:Makefile†L13-L18】
5. Build the student self-service views (`/me`, `/me/results`) with strict ownership checks and templates per the charter.【F:server/config/urls.py†L17-L23】
6. Implement admin/operator flows for CSV upload → preview → publish, including result publish toggles and export endpoints.【F:server/apps/results/views.py†L1-L3】【F:server/apps/results/admin.py†L1-L33】
7. Harden the deployment story by exercising migrations and verifying OAuth credentials wiring once the above blockers are resolved.【F:server/config/settings.py†L1-L120】

## Execution Plan

1. **Domain Model Repair**
   - Recreate `StudentQuerySet`/`StudentManager` with `.active()` filtering `Status.ACTIVE` and attach it to the model.
   - Add `Status` `TextChoices` with `.ACTIVE`/`.INACTIVE`, matching migrations/tests, plus `values` for importer validation.
   - Introduce convenience properties (`is_active`, `full_name`) and enforce `official_email` normalisation in `clean()` to keep data consistent.

2. **CSV Import Infrastructure**
   - Implement `_get_import_type` returning `ImportBatch.ImportType.STUDENTS` and drop unused imports in `StudentCSVImporter`.
   - Add pre-import caches for emails/roll numbers at class initialisation rather than during `_process_row` to keep state predictable.
   - Create Django management commands that accept CSV paths, support `--dry-run/--commit`, and print structured summaries.

3. **Test Suite Restoration**
   - Fix `ResultCSVImporterTests.setUp` to instantiate staff users, baseline students, and seed an existing result; import `datetime`/`date` explicitly.
   - Expand tests to cover CLI commands (preview vs. commit) once implemented, ensuring failure paths emit non-zero exit codes.
   - Add regression cases for student self-service views once built (ownership guard, unpublished results hidden).

4. **Feature Delivery**
   - Implement `/me` and `/me/results` views in `results` app using class-based views scoped to the authenticated student, with templates under `templates/results/`.
   - Build admin-friendly pages for uploading CSVs with server-side preview tables and “publish” toggles; reuse importer summaries for feedback.
   - Extend `Result` model with publish/unpublish service methods and integrate into admin actions.

5. **Operational Hardening**
   - Wire Makefile targets to the new management commands and document sample usage in `README.md`.
   - Add smoke tests covering Google OAuth domain rejection (feature flagged for CI by stubbing pipeline hooks).
   - Run `manage.py check --deploy`, `pytest`, and test CSV commands to ensure the deployment bundle is production-ready.

Once the above tasks are complete, regroup for a final audit covering security (CSRF, secure cookies), logging, and deployment automation as required by the project charter.
