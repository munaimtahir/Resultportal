"""Custom pipeline steps for social-auth Google Workspace login."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from social_core.exceptions import AuthForbidden

from .models import Student


def _normalize_email(email: str | None) -> str:
    if not email:
        raise AuthForbidden("accounts", _("Missing email address from Google response."))
    return email.strip().lower()


def enforce_workspace_domain(
    backend: Any,
    details: dict[str, Any],
    response: dict[str, Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """Block authentication if the Google account is outside the allowed domain."""

    allowed_domain = getattr(settings, "GOOGLE_WORKSPACE_DOMAIN", "pmc.edu.pk").lower()
    email = _normalize_email(details.get("email"))
    domain = email.split("@")[-1]
    if domain != allowed_domain:
        raise AuthForbidden(
            backend,
            _("Access restricted to {domain} accounts.").format(domain=allowed_domain),
        )


@transaction.atomic
def associate_student_profile(
    backend: Any,
    user: Any,
    response: dict[str, Any],
    details: dict[str, Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """Link the authenticated user to a ``Student`` profile by email."""

    email = _normalize_email(details.get("email"))

    # Superusers/staff can authenticate even without a Student record to
    # accommodate administrative accounts that will be provisioned later.
    if user and (user.is_staff or user.is_superuser):
        Student.objects.update_or_create(
            official_email=email,
            defaults={"user": user},
        )
        return

    try:
        student = Student.objects.select_for_update().get(official_email__iexact=email)
    except Student.DoesNotExist as exc:  # pragma: no cover - defensive
        raise PermissionDenied(
            _("No student record is registered for {email}.").format(email=email)
        ) from exc

    if student.user and student.user != user:
        # If the student was previously linked to another account, prevent takeover.
        raise PermissionDenied(
            _("This student account is already linked to another user."),
        )

    student.user = user
    student.save(update_fields=["user", "updated_at"])
