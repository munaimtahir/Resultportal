"""Accounts domain models.

Stage 1 introduces a minimal ``Student`` record that is linked to the Django
``User`` model via a one-to-one relationship. Later stages will expand the
schema, but for Google Workspace login we only need to be able to associate an
authenticated user with the institutional email address that was provisioned in
the CSV imports.
"""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class StudentQuerySet(models.QuerySet):
    """Custom queryset helpers for ``Student`` records."""

    def active(self) -> "StudentQuerySet":
        return self.filter(status=Student.Status.ACTIVE)

    def inactive(self) -> "StudentQuerySet":
        return self.filter(status=Student.Status.INACTIVE)


class Student(models.Model):
    """Represents a student that is allowed to access the result portal."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    roll_number_validator = RegexValidator(
        regex=r"^[A-Za-z0-9_-]+$",
        message="Roll numbers may only contain letters, numbers, dashes or underscores.",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="student_profile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Linked Django user once the student logs in via Google.",
    )
    roll_number = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        validators=[roll_number_validator],
        help_text="Unique roll number assigned by the institution.",
    )
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    display_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Full name as it should appear on result slips.",
    )
    official_email = models.EmailField(
        unique=True,
        help_text="Institutional email used for Google Workspace login.",
    )
    recovery_email = models.EmailField(
        blank=True,
        help_text="Optional personal email for roster recovery communications.",
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
        help_text="Whether the student account is active on the portal.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StudentQuerySet.as_manager()

    class Meta:
        ordering = ("official_email",)
        indexes = [
            models.Index(fields=("roll_number",), name="student_roll_number_idx"),
            models.Index(fields=("status",), name="student_status_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.official_email

    @property
    def is_active(self) -> bool:
        """Return whether the student is marked as active in the roster."""

        return self.status == self.Status.ACTIVE
