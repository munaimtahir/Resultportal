"""Accounts domain models.

Stage 1 introduces a minimal ``Student`` record that is linked to the Django
``User`` model via a one-to-one relationship. Later stages will expand the
schema, but for Google Workspace login we only need to be able to associate an
authenticated user with the institutional email address that was provisioned in
the CSV imports.
"""

from django.conf import settings

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="student_profile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Linked Django user once the student logs in via Google.",
    )

    official_email = models.EmailField(
        unique=True,
        help_text="Institutional email used for Google Workspace login.",
    )

