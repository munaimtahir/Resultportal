"""CSV import workflow for examination results."""

from __future__ import annotations

import csv
from contextlib import nullcontext
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import IO, Iterable, Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import Student
from apps.core.importers import ImportSummary, RowResult

from .models import ImportBatch, Result


class ResultCSVImporter:
    """Import subject-wise results from the canonical ``results.csv`` feed."""

    REQUIRED_COLUMNS = (
        "roll_no",
        "name",
        "block",
        "year",
        "subject",
        "written_marks",
        "viva_marks",
        "total_marks",
        "grade",
        "exam_date",
    )
    OPTIONAL_COLUMNS = ("respondent_id",)

    def __init__(
        self,
        stream: IO[str],
        *,
        started_by=None,
        filename: str | None = None,
        notes: str | None = None,
    ) -> None:
        self.stream = stream
        self.started_by = started_by
        self.filename = filename or ""
        self.notes = notes or ""

    def preview(self) -> ImportSummary:
        return self._process(dry_run=True)

    def commit(self) -> ImportSummary:
        return self._process(dry_run=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _process(self, *, dry_run: bool) -> ImportSummary:
        self._rewind_stream()
        reader = csv.DictReader(self.stream)
        self._validate_headers(reader.fieldnames)

        batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            started_by=self.started_by,
            source_filename=self.filename,
            notes=self.notes,
            is_dry_run=dry_run,
        )

        row_results: list[RowResult] = []
        created = updated = skipped = 0
        seen_keys: set[tuple[str, str, date]] = set()

        context = transaction.atomic() if not dry_run else nullcontext()
        with context:
            for row_number, raw_row in enumerate(reader, start=2):
                normalised = {key: (value or "").strip() for key, value in raw_row.items()}
                row_result = RowResult(row_number=row_number, action="skipped", data=normalised)

                errors = self._validate_basic_fields(normalised)
                if errors:
                    row_result.errors.extend(errors)
                    skipped += 1
                    row_results.append(row_result)
                    continue

                parsed = self._parse_row(normalised)
                if isinstance(parsed, list):
                    row_result.errors.extend(parsed)
                    skipped += 1
                    row_results.append(row_result)
                    continue

                payload, composite_key = parsed
                if composite_key in seen_keys:
                    row_result.errors.append(
                        "Duplicate roll_no/subject/exam_date combination within file.",
                    )
                    skipped += 1
                    row_results.append(row_result)
                    continue
                seen_keys.add(composite_key)

                student = Student.objects.filter(roll_number__iexact=payload["roll_number"]).first()
                if not student:
                    row_result.errors.append(
                        f"Student with roll number {payload['roll_number']} not found.",
                    )
                    skipped += 1
                    row_results.append(row_result)
                    continue

                result = Result.objects.filter(
                    student=student,
                    subject=payload["subject"],
                    exam_date=payload["exam_date"],
                ).first()

                validation_errors = self._validate_against_model(result, student, payload, batch)
                if validation_errors:
                    row_result.errors.extend(validation_errors)
                    skipped += 1
                    row_results.append(row_result)
                    continue

                if result is None:
                    row_result.action = "created"
                    created += 1
                    if not dry_run:
                        self._create_result(student, payload, batch)
                else:
                    row_result.action = "updated"
                    changes = self._update_result(result, payload, batch, dry_run)
                    if not changes:
                        row_result.messages.append("No changes detected; record already up to date.")
                    elif dry_run:
                        row_result.messages.append(
                            f"Would apply {len(changes)} field change(s)."
                        )
                    else:
                        row_result.messages.append(
                            f"Applied {len(changes)} field change(s)."
                        )
                    updated += 1

                row_results.append(row_result)

            batch.row_count = len(row_results)
            batch.created_rows = created
            batch.updated_rows = updated
            batch.skipped_rows = skipped
            batch.save(
                update_fields=[
                    "row_count",
                    "created_rows",
                    "updated_rows",
                    "skipped_rows",
                ]
            )

            if not dry_run:
                batch.mark_completed()

        return ImportSummary(
            batch=batch,
            created=created,
            updated=updated,
            skipped=skipped,
            row_results=row_results,
        )

    def _validate_headers(self, headers: Optional[Iterable[str]]) -> None:
        if not headers:
            raise ValueError("results.csv must include a header row.")

        header_set = {header.strip() for header in headers if header}
        missing = [column for column in self.REQUIRED_COLUMNS if column not in header_set]
        if missing:
            raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    def _validate_basic_fields(self, row: dict[str, str]) -> list[str]:
        errors: list[str] = []
        for column in self.REQUIRED_COLUMNS:
            if not row.get(column):
                errors.append(f"{column} is required.")
        return errors

    def _parse_row(
        self, row: dict[str, str]
    ) -> tuple[dict[str, object], tuple[str, str, date]] | list[str]:
        errors: list[str] = []

        try:
            year = int(row["year"])
        except ValueError:
            errors.append("year must be an integer.")
            year = None

        try:
            exam_date = date.fromisoformat(row["exam_date"])
        except ValueError:
            errors.append("exam_date must be in YYYY-MM-DD format.")
            exam_date = None

        written = self._parse_decimal(row["written_marks"], "written_marks", errors)
        viva = self._parse_decimal(row["viva_marks"], "viva_marks", errors)
        total = self._parse_decimal(row["total_marks"], "total_marks", errors)

        if errors:
            return errors

        payload = {
            "respondent_id": row.get("respondent_id", ""),
            "roll_number": row["roll_no"],
            "name": row["name"],
            "block": row["block"],
            "year": year,
            "subject": row["subject"],
            "written_marks": written,
            "viva_marks": viva,
            "total_marks": total,
            "grade": row["grade"],
            "exam_date": exam_date,
        }

        key = (row["roll_no"].lower(), row["subject"].lower(), exam_date)
        return payload, key

    def _parse_decimal(
        self, value: str, field: str, errors: list[str]
    ) -> Decimal | None:
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            errors.append(f"{field} must be a numeric value.")
            return None

    def _validate_against_model(
        self,
        result: Result | None,
        student: Student,
        payload: dict[str, object],
        batch: ImportBatch,
    ) -> list[str]:
        if result is None:
            candidate = Result(student=student, import_batch=batch, **payload)
            try:
                candidate.full_clean()
            except ValidationError as exc:  # pragma: no cover - exercised in tests
                return _flatten_validation_errors(exc)
            return []

        tracked_fields = (
            "respondent_id",
            "roll_number",
            "name",
            "block",
            "year",
            "subject",
            "written_marks",
            "viva_marks",
            "total_marks",
            "grade",
            "exam_date",
        )
        original_values = {field: getattr(result, field) for field in tracked_fields}
        original_batch = result.import_batch

        for field in tracked_fields:
            setattr(result, field, payload[field])
        result.import_batch = batch

        try:
            result.full_clean()
        except ValidationError as exc:  # pragma: no cover - exercised in tests
            errors = _flatten_validation_errors(exc)
        else:
            errors = []
        finally:
            for field, value in original_values.items():
                setattr(result, field, value)
            result.import_batch = original_batch

        return errors

    def _create_result(
        self, student: Student, payload: dict[str, object], batch: ImportBatch
    ) -> Result:
        result = Result(student=student, import_batch=batch, **payload)
        result.full_clean()
        result.save()
        return result

    def _update_result(
        self,
        result: Result,
        payload: dict[str, object],
        batch: ImportBatch,
        dry_run: bool,
    ) -> dict[str, tuple[object, object]]:
        tracked_fields = (
            "respondent_id",
            "roll_number",
            "name",
            "block",
            "year",
            "subject",
            "written_marks",
            "viva_marks",
            "total_marks",
            "grade",
            "exam_date",
        )
        changes: dict[str, tuple[object, object]] = {}

        for field in tracked_fields:
            new_value = payload[field]
            old_value = getattr(result, field)
            if old_value != new_value:
                changes[field] = (old_value, new_value)

