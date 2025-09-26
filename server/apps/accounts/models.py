"""Accounts domain models.

Stage 1 introduces a minimal ``Student`` record that is linked to the Django
``User`` model via a one-to-one relationship. Later stages will expand the
schema, but for Google Workspace login we only need to be able to associate an
authenticated user with the institutional email address that was provisioned in
the CSV imports.
"""

from __future__ import annotations

from django.conf import settings

    official_email = models.EmailField(
        unique=True,
        help_text="Institutional email used for Google Workspace login.",
    )
    roll_number = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,

        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9_-]+$",
                message="Roll numbers may only contain letters, numbers, dashes or underscores.",
            )
        ],

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
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("graduated", "Graduated"),
        ("suspended", "Suspended"),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Current status of the student (e.g., active, graduated, suspended).",
    )

    class Meta:
        ordering = ("official_email",)
        indexes = [
            models.Index(fields=["roll_number"], name="student_roll_number_idx"),
            models.Index(fields=["status"], name="student_status_idx"),
        ]