"""Accounts domain models.

Stage 1 introduces a minimal ``Student`` record that is linked to the Django
``User`` model via a one-to-one relationship. Later stages will expand the
schema, but for Google Workspace login we only need to be able to associate an
authenticated user with the institutional email address that was provisioned in
the CSV imports.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class StudentQuerySet(models.QuerySet):
    """Custom queryset providing convenience helpers."""

    def active(self) -> "StudentQuerySet":
        return self.filter(status=Student.Status.ACTIVE)


class StudentManager(models.Manager.from_queryset(StudentQuerySet)):
    """Manager wiring the custom queryset for type checkers."""

    pass


class Student(models.Model):
    """Student roster record sourced from the official CSV imports."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
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
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9_-]+$",
                message="Roll numbers may only contain letters, numbers, dashes or underscores.",
            )
        ],
        help_text="Unique roll number assigned by the institution.",
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
        help_text="Whether the student account is active on the portal.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StudentManager()

    class Meta:
        ordering = ("official_email",)
        indexes = [
            models.Index(fields=["roll_number"], name="student_roll_number_idx"),
            models.Index(fields=["status"], name="student_status_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.display_name or self.official_email

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    def clean(self) -> None:
        super().clean()

        if self.official_email:
            self.official_email = self.official_email.strip().lower()
            allowed_domain = getattr(settings, "GOOGLE_WORKSPACE_DOMAIN", "pmc.edu.pk").lower()
            domain = self.official_email.split("@")[-1]
            if domain != allowed_domain:
                raise ValidationError(
                    {
                        "official_email": _(
                            "Official email must belong to the {domain} workspace."
                        ).format(domain=allowed_domain)
                    }
                )

        if self.roll_number:
            self.roll_number = self.roll_number.strip()

    def save(self, *args, validate=True, **kwargs):
        if validate:
            self.full_clean()
        return super().save(*args, **kwargs)
