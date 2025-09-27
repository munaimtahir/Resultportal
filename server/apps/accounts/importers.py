"""CSV import workflow for student roster data."""

from __future__ import annotations

import csv
from contextlib import nullcontext
from typing import IO, Iterable, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.importers import BaseCSVImporter, ImportSummary, RowResult, flatten_validation_errors
from apps.results.models import ImportBatch

from .models import Student


class StudentCSVImporter(BaseCSVImporter):
    """Import students from the canonical ``students.csv`` payload."""

    REQUIRED_COLUMNS = (
        "roll_no",
        "first_name",
        "last_name",
        "display_name",
        "official_email",
    )
    OPTIONAL_COLUMNS = ("recovery_email", "batch_code", "status")

    def _validate_headers(self, headers: Optional[Iterable[str]]) -> None:
        """Validate that required CSV headers are present."""
        if not headers:
            raise ValueError("students.csv must include a header row.")

        header_set = {header.strip() for header in headers if header}
        missing = [column for column in self.REQUIRED_COLUMNS if column not in header_set]
        if missing:
            raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    def _process_row(
        self, row_number: int, normalised: dict[str, str], dry_run: bool, batch: ImportBatch
    ) -> tuple[str, int, int, int, RowResult]:
        """Process a single student row."""
        row_result = RowResult(row_number=row_number, action="skipped", data=normalised)

        # Track seen values within this import
        if not hasattr(self, '_seen_roll_numbers'):
            self._seen_roll_numbers: set[str] = set()
        if not hasattr(self, '_seen_emails'):
            self._seen_emails: set[str] = set()

        errors = self._validate_basic_fields(normalised, self._seen_roll_numbers, self._seen_emails)
        if errors:
            row_result.errors.extend(errors)
            return "skipped", 0, 0, 1, row_result

        roll_number = normalised["roll_no"]
        student = Student.objects.filter(roll_number__iexact=roll_number).first()
        data = self._build_student_payload(normalised)

        validation_errors = self._validate_against_model(student, data)
        if validation_errors:
            row_result.errors.extend(validation_errors)
            return "skipped", 0, 0, 1, row_result

        if student is None:
            row_result.action = "created"
            if not dry_run:
                self._create_student(data)
            return "created", 1, 0, 0, row_result
        else:
            row_result.action = "updated"
            changes = self._update_student(student, data, dry_run)
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
            return "updated", 0, 1, 0, row_result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _validate_basic_fields(
        self,
        row: dict[str, str],
        seen_roll_numbers: set[str],
        seen_emails: set[str],
    ) -> list[str]:
        errors: list[str] = []

        roll_number = row.get("roll_no", "")
        if not roll_number:
            errors.append("roll_no is required.")
        else:
            canonical_roll = roll_number.lower()
            if canonical_roll in seen_roll_numbers:
                errors.append("Duplicate roll_no found within file.")
            else:
                seen_roll_numbers.add(canonical_roll)

        official_email = row.get("official_email", "").lower()
        if not official_email:
            errors.append("official_email is required.")
        else:
            domain = official_email.split("@")[-1]
            allowed_domain = settings.GOOGLE_WORKSPACE_DOMAIN.lower()
            if domain != allowed_domain:
                errors.append(
                    f"official_email must belong to {allowed_domain}.",
                )
            canonical_email = official_email
            if canonical_email in seen_emails:
                errors.append("Duplicate official_email found within file.")
            else:
                seen_emails.add(canonical_email)

        for column in ("first_name", "last_name", "display_name"):
            if not row.get(column):
                errors.append(f"{column} is required.")

        return errors

    def _normalize_status(self, raw_status: str | None) -> str:
        value = (raw_status or "").strip().lower()
        if not value:
            return Student.Status.ACTIVE
        if value in Student.Status.values:
            return value
        return Student.Status.ACTIVE

    def _build_student_payload(self, row: dict[str, str]) -> dict[str, str]:
        return {
            "roll_number": row.get("roll_no", ""),
            "first_name": row.get("first_name", ""),
            "last_name": row.get("last_name", ""),
            "display_name": row.get("display_name", ""),
            "official_email": row.get("official_email", "").lower(),
            "recovery_email": row.get("recovery_email", ""),
            "batch_code": row.get("batch_code", ""),
            "status": self._normalize_status(row.get("status", "")),
        }

    def _validate_against_model(
        self, student: Student | None, data: dict[str, str]
    ) -> list[str]:
        if student is None:
            candidate = Student(**data)
            try:
                candidate.full_clean()
            except ValidationError as exc:  # pragma: no cover - exercised in tests
                return flatten_validation_errors(exc)
            return []

        original_values = {field: getattr(student, field) for field in data.keys()}
        for field, value in data.items():
            setattr(student, field, value)
        try:
            student.full_clean()
        except ValidationError as exc:  # pragma: no cover - exercised in tests
            errors = flatten_validation_errors(exc)
        else:
            errors = []
        finally:
            for field, value in original_values.items():
                setattr(student, field, value)
        return errors

    def _create_student(self, data: dict[str, str]) -> Student:
        student = Student(**data)
        student.full_clean()
        student.save()
        return student

    def _update_student(
        self, student: Student, data: dict[str, str], dry_run: bool
    ) -> dict[str, tuple[str, str]]:
        tracked_fields = (
            "first_name",
            "last_name",
            "display_name",
            "official_email",
            "recovery_email",
            "batch_code",
            "status",
        )
        changes: dict[str, tuple[str, str]] = {}
        original: dict[str, str] = {}

        for field in tracked_fields:
            new_value = data.get(field, "")
            old_value = getattr(student, field)
            if old_value != new_value:
                changes[field] = (old_value, new_value)
                original[field] = old_value

        if dry_run or not changes:
            return changes

        for field, (_, new_value) in changes.items():
            setattr(student, field, new_value)

        student.full_clean()
        student.save()
        return changes
