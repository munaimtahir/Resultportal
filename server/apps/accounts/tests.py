"""Tests for Google Workspace authentication helpers."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from social_core.exceptions import AuthForbidden

from .models import Student
from . import pipeline



class WorkspacePipelineTests(TestCase):
    def setUp(self) -> None:
        self.backend = "google-oauth2"
        self.details = {"email": f"student@{settings.GOOGLE_WORKSPACE_DOMAIN}"}

    def test_enforce_workspace_domain_allows_allowed_domain(self) -> None:
        pipeline.enforce_workspace_domain(self.backend, self.details, {})

    def test_enforce_workspace_domain_rejects_other_domain(self) -> None:
        with self.assertRaises(AuthForbidden):
            pipeline.enforce_workspace_domain(
                self.backend,
                {"email": "intruder@example.com"},
                {},
            )

    def test_associate_student_links_existing_profile(self) -> None:
        user = get_user_model().objects.create_user(
            username="alice",
            email=self.details["email"],
        )
in

        pipeline.associate_student_profile(
            self.backend,
            user=user,
            response={},
            details=self.details,
        )

        student.refresh_from_db()
        self.assertEqual(student.user, user)

    def test_associate_student_blocks_takeover(self) -> None:
        original_user = get_user_model().objects.create_user(
            username="bob",
            email=self.details["email"],
        )
        other_user = get_user_model().objects.create_user(
            username="charlie",
            email=self.details["email"],
        )

        with self.assertRaises(PermissionDenied):
            pipeline.associate_student_profile(
                self.backend,
                user=other_user,
                response={},
                details=self.details,
            )

    def test_associate_student_requires_registered_email(self) -> None:
        user = get_user_model().objects.create_user(
            username="dana",
            email=self.details["email"],
        )

        with self.assertRaises(PermissionDenied):
            pipeline.associate_student_profile(
                self.backend,
                user=user,
                response={},
                details=self.details,
            )

    def test_staff_user_creates_placeholder_student(self) -> None:
        staff_user = get_user_model().objects.create_user(
            username="eve",
            email=self.details["email"],
            is_staff=True,
        )

        pipeline.associate_student_profile(
            self.backend,
            user=staff_user,
            response={},
            details=self.details,
        )

        student = Student.objects.get(official_email=self.details["email"])
        self.assertEqual(student.user, staff_user)

