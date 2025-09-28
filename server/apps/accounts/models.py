"""Accounts domain models."""

from __future__ import annotations


from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models 


class StudentQuerySet(models.QuerySet["Student"]):
    """Custom queryset with helpers used by the importer and pipeline."""

    def active(self) -> "StudentQuerySet":
        """Return only students whose status is ``ACTIVE``."""

        return self.filter(status=Student.Status.ACTIVE)


class Student(models.Model):
    """Student record linked to Django ``User`` via a one-to-one relationship."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    objects = StudentQuerySet.as_manager()

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

    @property
    def is_active(self) -> bool:
        """Check if the student is in active status."""
        return self.status == self.Status.ACTIVE

    def get_status_display(self) -> str:
        """Get human-readable status display (Django provides this automatically)."""
        return dict(self.Status.choices)[self.status]
