
import io

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from social_core.exceptions import AuthForbidden

from .models import Student


class StudentModelTests(TestCase):
    def test_status_helpers(self) -> None:
        active = Student.objects.create(
            official_email="active@pmc.edu.pk",
            roll_number="A-1",
            status=Student.Status.ACTIVE,
        )
        inactive = Student.objects.create(
            official_email="inactive@pmc.edu.pk",
            roll_number="B-2",
            status=Student.Status.INACTIVE,
        )

        self.assertIn(active, Student.objects.active())
        self.assertNotIn(inactive, Student.objects.active())
        self.assertTrue(active.is_active)
        self.assertFalse(inactive.is_active)


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
        self.assertEqual(student.status, Student.Status.ACTIVE)
        self.assertEqual(student.display_name, staff_user.username)


class StudentCSVImporterTests(TestCase):
    def setUp(self) -> None:
        self.staff_user = get_user_model().objects.create_user(
            username="importer",
            email=f"importer@{settings.GOOGLE_WORKSPACE_DOMAIN}",
            is_staff=True,
        )
        self.existing = Student.objects.create(
            roll_number="PMC-001",
            first_name="Alice",
            last_name="Existing",
            display_name="Alice Existing",
            official_email="alice@pmc.edu.pk",
            batch_code="b28",
        )

        self.csv_payload = """roll_no,first_name,last_name,display_name,official_email,recovery_email,batch_code,status
PMC-001,Alice,Smith,Alice Smith,alice@pmc.edu.pk,,b29,active
PMC-002,Bob,Jones,Bob Jones,bob@pmc.edu.pk,,b29,active
PMC-003,Charlie,Brown,Charlie Brown,charlie@gmail.com,,b29,active
"""

    def _build_stream(self) -> io.StringIO:
        return io.StringIO(self.csv_payload)

    def test_preview_reports_validation_errors_without_mutating(self) -> None:
        importer = StudentCSVImporter(
            self._build_stream(),
            started_by=self.staff_user,
            filename="students.csv",
        )

        summary = importer.preview()

        self.assertTrue(summary.batch.is_dry_run)
        self.assertEqual(summary.created, 1)
        self.assertEqual(summary.updated, 1)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.row_count, 3)
        self.assertEqual(Student.objects.count(), 1)

        updated_row = summary.row_results[0]
        self.assertEqual(updated_row.action, "updated")
        self.assertIn("Would apply", " ".join(updated_row.messages))

        invalid_row = summary.row_results[-1]
        self.assertTrue(invalid_row.has_errors)
        self.assertIn("official_email must belong", invalid_row.errors[0])

    def test_commit_creates_and_updates_students(self) -> None:
        importer = StudentCSVImporter(self._build_stream(), started_by=self.staff_user)

        summary = importer.commit()

        self.assertFalse(summary.batch.is_dry_run)
        self.assertIsNotNone(summary.batch.completed_at)
        self.assertEqual(summary.created, 1)
        self.assertEqual(summary.updated, 1)
        self.assertEqual(summary.skipped, 1)

        students = Student.objects.order_by("roll_number")
        self.assertEqual(students.count(), 2)

        updated_student = students.first()
        self.assertEqual(updated_student.last_name, "Smith")
        self.assertEqual(updated_student.display_name, "Alice Smith")
        self.assertEqual(updated_student.batch_code, "b29")

        new_student = students.last()
        self.assertEqual(new_student.roll_number, "PMC-002")
        self.assertEqual(new_student.display_name, "Bob Jones")

        # Invalid row should not create a record
        self.assertFalse(Student.objects.filter(roll_number="PMC-003").exists())

    def test_status_normalization_consistency(self) -> None:
        """Test that status values are consistently normalized to string values."""
        # Create a mock importer to test the helper method
        importer = StudentCSVImporter(io.StringIO(""), started_by=self.staff_user)

        # Test the helper method directly
        test_cases = [
            ("", "active"),  # Empty should default to active
            ("  ", "active"),  # Whitespace should default to active
            ("ACTIVE", "active"),  # Uppercase should normalize
            ("inactive", "inactive"),  # Lowercase should remain
            ("INACTIVE", "inactive"),  # Uppercase inactive should normalize
            ("invalid", "active"),  # Invalid should default to active
        ]

        for input_status, expected in test_cases:
            result = importer._normalize_status(input_status)
            self.assertIsInstance(result, str, f"Result should be string, got {type(result)}")
            self.assertEqual(result, expected, f"Input {input_status!r} should normalize to {expected!r}")
            self.assertIn(result, Student.Status.values, f"Result {result!r} should be a valid status")

        # Test with a single valid row to ensure the fix works end-to-end
        test_importer = StudentCSVImporter(
            io.StringIO(
                "roll_no,first_name,last_name,display_name,official_email,status\n"
                "PMC-TEST,John,Doe,John Doe,johndoe@pmc.edu.pk,\n"  # Empty status should default to active
            ),
            started_by=self.staff_user,
            filename="test_status.csv"
        )
        
        summary = test_importer.commit()
        self.assertEqual(summary.created, 1)
        self.assertEqual(summary.skipped, 0)
        
        # Verify the student was created with correct status
        student = Student.objects.get(roll_number="PMC-TEST")
        self.assertEqual(student.status, "active")
        self.assertIsInstance(student.status, str, "Student status should be string")
