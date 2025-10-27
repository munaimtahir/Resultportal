from __future__ import annotations
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Student, YearClass


class Exam(models.Model):
    """Exam/Assessment definition."""

    class ExamKind(models.TextChoices):
        BLOCK = "BLOCK", "Block Exam"
        SEND_UP = "SEND_UP", "Send-up Exam"
        UNIVERSITY = "UNIVERSITY", "University Exam"
        TEST = "TEST", "Test"

    year_class = models.ForeignKey(
        YearClass,
        on_delete=models.PROTECT,
        related_name="exams",
        help_text="Year/class this exam is for",
    )
    code = models.CharField(
        max_length=50, unique=True, help_text="Unique exam code (e.g., 'BLOCK-E-2024')"
    )
    title = models.CharField(max_length=200, help_text="Full exam title")
    kind = models.CharField(
        max_length=20,
        choices=ExamKind.choices,
        default=ExamKind.BLOCK,
        help_text="Type of examination",
    )
    block_letter = models.CharField(
        max_length=5, blank=True, help_text="Block letter (A, B, C, etc.) if applicable"
    )
    exam_date = models.DateField(help_text="Primary exam date")
    recheck_form_url = models.URLField(blank=True, help_text="URL to recheck application form")
    recheck_deadline = models.DateTimeField(
        null=True, blank=True, help_text="Deadline for recheck requests"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-exam_date", "code")
        indexes = [
            models.Index(fields=["code"], name="exam_code_idx"),
            models.Index(fields=["year_class", "exam_date"], name="exam_year_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.title}"

    def is_recheck_open(self) -> bool:
        """Check if recheck window is currently open."""
        if not self.recheck_deadline:
            return False
        return timezone.now() < self.recheck_deadline


class ImportBatch(models.Model):
    """Audit trail for roster/result CSV imports."""

    class ImportType(models.TextChoices):
        STUDENTS = "students", "Students"
        RESULTS = "results", "Results"

    import_type = models.CharField(max_length=20, choices=ImportType.choices)
    exam = models.ForeignKey(
        Exam,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="import_batches",
        help_text="Exam this batch is associated with (for result imports)",
    )
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
    csv_filename = models.CharField(
        max_length=255,
        blank=True,
        help_text="CSV filename for reference",
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
    errors_json = models.JSONField(
        default=list, blank=True, help_text="List of error messages from validation"
    )
    warnings_json = models.JSONField(
        default=list, blank=True, help_text="List of warning messages from validation"
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
        return self.filter(status=Result.ResultStatus.PUBLISHED)

    def by_status(self, status: str) -> "ResultQuerySet":
        return self.filter(status=status)


class Result(models.Model):
    """Stores a single subject result for a student."""

    class ResultStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        RETURNED = "RETURNED", "Returned"
        VERIFIED = "VERIFIED", "Verified"
        PUBLISHED = "PUBLISHED", "Published"

    student = models.ForeignKey(
        Student,
        related_name="results",
        on_delete=models.CASCADE,
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="results",
        help_text="Exam this result belongs to",
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
        help_text=(
            "Roll number as it appears in the import data, "
            "should match the student's roll number."
        ),
    )
    name = models.CharField(max_length=255)
    block = models.CharField(max_length=32)
    year = models.PositiveIntegerField()
    subject = models.CharField(max_length=128)

    # Marks fields - now mapped to theory/practical/total
    theory = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Theory/written component marks",
    )
    practical = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Practical/viva component marks",
    )
    total = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, help_text="Total marks"
    )

    # Keep old field names for backward compatibility
    written_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    viva_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    grade = models.CharField(max_length=32)
    exam_date = models.DateField()

    # Workflow status fields
    status = models.CharField(
        max_length=20,
        choices=ResultStatus.choices,
        default=ResultStatus.DRAFT,
        help_text="Current workflow status",
    )
    status_log = models.JSONField(
        default=list, blank=True, help_text="Audit trail of status changes"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_results",
        help_text="Admin who verified this result",
    )
    verified_at = models.DateTimeField(null=True, blank=True, help_text="When result was verified")
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
        return self.status == self.ResultStatus.PUBLISHED

    def clean(self) -> None:
        errors: dict[str, list[str]] = {}

        # Sync old fields to new if they're set and new fields aren't
        if self.written_marks is not None and not hasattr(self, "_theory_set"):
            self.theory = self.written_marks
        if self.viva_marks is not None and not hasattr(self, "_practical_set"):
            self.practical = self.viva_marks
        if self.total_marks is not None and not hasattr(self, "_total_set"):
            self.total = self.total_marks

        # Validate marks are non-negative
        for field in ("theory", "practical", "total", "written_marks", "viva_marks", "total_marks"):
            value = getattr(self, field, None)
            if value is not None and value < 0:
                errors.setdefault(field, []).append("Marks cannot be negative.")

        # Check total = theory + practical (if all are set)
        if self.theory is not None and self.practical is not None and self.total is not None:
            expected = (Decimal(self.theory) + Decimal(self.practical)).quantize(Decimal("0.01"))
            total = Decimal(self.total).quantize(Decimal("0.01"))
            if expected != total:
                errors.setdefault("total", []).append(
                    "Total marks must equal theory plus practical marks.",
                )

        # Backward compatibility check (only if new fields not set)
        if (
            self.theory is None
            and self.written_marks is not None
            and self.viva_marks is not None
            and self.total_marks is not None
        ):
            expected = (Decimal(self.written_marks) + Decimal(self.viva_marks)).quantize(
                Decimal("0.01")
            )
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
        # Sync fields bidirectionally
        # Priority: use written_marks/viva_marks/total_marks
        # if theory/practical/total not explicitly set
        if self.theory is not None:
            self.written_marks = self.theory
        elif self.written_marks is not None:
            self.theory = self.written_marks

        if self.practical is not None:
            self.viva_marks = self.practical
        elif self.viva_marks is not None:
            self.practical = self.viva_marks

        if self.total is not None:
            self.total_marks = self.total
        elif self.total_marks is not None:
            self.total = self.total_marks

        self.full_clean()
        return super().save(*args, **kwargs)

    def _log_status_change(self, old_status: str, new_status: str, user=None) -> None:
        """Add status change to audit log."""
        log_entry = {
            "timestamp": timezone.now().isoformat(),
            "from_status": old_status,
            "to_status": new_status,
            "user": user.username if user else None,
        }
        if not isinstance(self.status_log, list):
            self.status_log = []
        self.status_log.append(log_entry)

    def submit(self, user=None) -> None:
        """Transition from DRAFT to SUBMITTED."""
        if self.status == self.ResultStatus.DRAFT:
            old_status = self.status
            self.status = self.ResultStatus.SUBMITTED
            self._log_status_change(old_status, self.status, user)
            self.save(update_fields=["status", "status_log", "updated_at"])

    def return_for_correction(self, user=None) -> None:
        """Transition from SUBMITTED to RETURNED."""
        if self.status == self.ResultStatus.SUBMITTED:
            old_status = self.status
            self.status = self.ResultStatus.RETURNED
            self._log_status_change(old_status, self.status, user)
            self.save(update_fields=["status", "status_log", "updated_at"])

    def verify(self, user) -> None:
        """Transition from SUBMITTED to VERIFIED."""
        if self.status == self.ResultStatus.SUBMITTED:
            old_status = self.status
            self.status = self.ResultStatus.VERIFIED
            self.verified_by = user
            self.verified_at = timezone.now()
            self._log_status_change(old_status, self.status, user)
            self.save(
                update_fields=["status", "verified_by", "verified_at", "status_log", "updated_at"]
            )

    def publish(self, user=None) -> None:
        """Mark this result as published, making it visible to students."""
        if self.status == self.ResultStatus.VERIFIED:
            old_status = self.status
            self.status = self.ResultStatus.PUBLISHED
            self.published_at = timezone.now()
            self._log_status_change(old_status, self.status, user)
            self.save(update_fields=["status", "published_at", "status_log", "updated_at"])

    def unpublish(self, user=None) -> None:
        """Mark this result as unpublished, hiding it from students."""
        if self.status == self.ResultStatus.PUBLISHED:
            old_status = self.status
            self.status = self.ResultStatus.VERIFIED
            self.published_at = None
            self._log_status_change(old_status, self.status, user)
            self.save(update_fields=["status", "published_at", "status_log", "updated_at"])
