from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Student


class ImportBatch(models.Model):
    """Audit trail for roster/result CSV imports."""

    class ImportType(models.TextChoices):
        STUDENTS = "students", "Students"
        RESULTS = "results", "Results"

    import_type = models.CharField(max_length=20, choices=ImportType.choices)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="import_batches",
        help_text="Staff user that initiated the import (if authenticated).",
    )
    source_filename = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original filename uploaded by the operator.",
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional operator notes or contextual metadata.",
    )
    is_dry_run = models.BooleanField(
        default=True,
        help_text="Marks whether this batch represents a dry-run preview.",
    )
    row_count = models.PositiveIntegerField(
        default=0,
        help_text="Total rows processed in the import payload.",
    )
    created_rows = models.PositiveIntegerField(
        default=0,
        help_text="Number of records that would be newly created.",
    )
    updated_rows = models.PositiveIntegerField(
        default=0,
        help_text="Number of records that would be updated.",
    )
    skipped_rows = models.PositiveIntegerField(
        default=0,
        help_text="Rows skipped due to validation errors.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the import was finalised (if applicable).",
    )

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.get_import_type_display()} import @ {self.created_at:%Y-%m-%d %H:%M:%S}"

    def mark_completed(self) -> None:
        """Mark the batch as executed, stamping the completion time."""

        if not self.completed_at:
            self.completed_at = timezone.now()
            self.is_dry_run = False
            self.save(update_fields=["completed_at", "is_dry_run"])


class ResultQuerySet(models.QuerySet):
    def published(self) -> "ResultQuerySet":
        return self.filter(published_at__isnull=False)


class Result(models.Model):
    """Stores a single subject result for a student."""

    student = models.ForeignKey(
        Student,
        related_name="results",
        on_delete=models.CASCADE,
    )
    import_batch = models.ForeignKey(
        ImportBatch,
        related_name="results",
        on_delete=models.PROTECT,
        help_text="Import batch that created or last updated this record.",
    )
    respondent_id = models.CharField(max_length=64, blank=True)
    roll_number = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Roll number as it appears in the import data, should match the student's roll number.",
    )
    name = models.CharField(max_length=255)
    block = models.CharField(max_length=32)
    year = models.PositiveIntegerField()
    subject = models.CharField(max_length=128)
    written_marks = models.DecimalField(max_digits=6, decimal_places=2)
    viva_marks = models.DecimalField(max_digits=6, decimal_places=2)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2)
    grade = models.CharField(max_length=32)
    exam_date = models.DateField()
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ResultQuerySet.as_manager()

    class Meta:
        ordering = ("-exam_date", "subject", "student_id")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "subject", "exam_date"),
                name="result_unique_student_subject_exam",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.student} – {self.subject} ({self.exam_date:%Y-%m-%d})"

    @property
    def is_published(self) -> bool:
        return self.published_at is not None

    def clean(self) -> None:
        errors: dict[str, list[str]] = {}

        for field in ("written_marks", "viva_marks", "total_marks"):
            value = getattr(self, field)
            if value is None:
                continue
            if value < 0:
                errors.setdefault(field, []).append("Marks cannot be negative.")

        if self.written_marks is not None and self.viva_marks is not None and self.total_marks is not None:
            expected = (Decimal(self.written_marks) + Decimal(self.viva_marks)).quantize(Decimal("0.01"))
            total = Decimal(self.total_marks).quantize(Decimal("0.01"))
            if expected != total:
                errors.setdefault("total_marks", []).append(
                    "Total marks must equal written plus viva marks.",
                )

        if self.student and self.student.roll_number and self.roll_number:
            if self.student.roll_number.lower() != self.roll_number.lower():
                errors.setdefault("roll_number", []).append(
                    _("Roll number does not match the linked student record."),
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
