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


class Student(models.Model):
    """A student registered at the institution."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    # Core identity fields
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

    # Personal information
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

    # Academic information
    batch_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Cohort identifier (e.g., b29).",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Whether the student account is active on the portal.",
    )

    # System fields
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile",
        help_text="Linked Django user once the student logs in via Google.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("official_email",)
        indexes = [
            models.Index(fields=["roll_number"], name="student_roll_number_idx"),
            models.Index(fields=["status"], name="student_status_idx"),
        ]

    def __str__(self):
        return f"{self.display_name or self.official_email} ({self.roll_number})"
