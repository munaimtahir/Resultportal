"""Accounts domain models."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class YearClass(models.Model):
    """Represents academic year/class (1st Year, 2nd Year, etc.)."""

    label = models.CharField(
        max_length=50,
        unique=True,
        help_text="Label for the year/class (e.g., '1st Year', 'Final Year')",
    )
    order = models.PositiveIntegerField(
        unique=True, help_text="Numeric order for sorting (1, 2, 3, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order",)
        verbose_name = "Year/Class"
        verbose_name_plural = "Year/Classes"

    def __str__(self) -> str:
        return self.label


class StudentQuerySet(models.QuerySet["Student"]):
    """Custom queryset with helpers used by the importer and pipeline."""

    def active(self) -> StudentQuerySet:
        """Return only students whose status is ``ACTIVE``."""

        return self.filter(status=Student.Status.ACTIVE)


class Student(models.Model):
    """Student record linked to Django ``User`` via a one-to-one relationship."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    objects = StudentQuerySet.as_manager()

    year_class = models.ForeignKey(
        YearClass,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="students",
        help_text="Academic year/class for this student",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile",
        help_text="Linked Django user once the student logs in via Google.",
    )
    official_email = models.EmailField(
        unique=True,
        help_text="Institutional email used for Google Workspace login.",
    )
    roll_number = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        help_text="Unique roll number assigned by the institution.",
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9_-]+$",
                message="Roll numbers may only contain letters, numbers, dashes or underscores.",
            )
        ],
    )
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    display_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Full name as it should appear on result slips.",
    )
    recovery_email = models.EmailField(
        blank=True,
        help_text="Optional personal email for roster recovery communications.",
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number for student access verification.",
    )
    batch_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Cohort identifier (e.g., b29).",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Current status of the student record.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("official_email",)
        indexes = [
            models.Index(fields=["roll_number"], name="student_roll_number_idx"),
            models.Index(fields=["status"], name="student_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["year_class", "roll_number"],
                name="unique_year_class_roll_number",
                condition=models.Q(year_class__isnull=False, roll_number__isnull=False),
            )
        ]

    def __str__(self) -> str:
        """Return string representation of Student."""
        if self.display_name:
            return f"{self.display_name} ({self.roll_number or self.official_email})"
        return self.roll_number or self.official_email

    @property
    def is_active(self) -> bool:
        """Check if the student is in active status."""
        return self.status == self.Status.ACTIVE


class StudentAccessToken(models.Model):
    """One-time access token for lightweight student authentication."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="access_tokens",
        help_text="Student this token belongs to",
    )
    code = models.CharField(max_length=64, unique=True, help_text="Unique access code")
    expires_at = models.DateTimeField(help_text="Token expiration timestamp")
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(
        null=True, blank=True, help_text="When this token was first used"
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["code"], name="access_token_code_idx"),
            models.Index(fields=["expires_at"], name="access_token_expires_idx"),
        ]

    def __str__(self) -> str:
        return f"Token for {self.student.roll_number} (expires {self.expires_at:%Y-%m-%d})"

    @classmethod
    def generate_for_student(
        cls, student: Student, validity_hours: int = 24
    ) -> StudentAccessToken:
        """Generate a new access token for a student."""
        code = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=validity_hours)
        return cls.objects.create(student=student, code=code, expires_at=expires_at)

    def is_valid(self) -> bool:
        """Check if token is still valid (not expired and not used)."""
        return timezone.now() < self.expires_at and self.used_at is None

    def mark_used(self) -> None:
        """Mark token as used."""
        if self.used_at is None:
            self.used_at = timezone.now()
            self.save(update_fields=["used_at"])
