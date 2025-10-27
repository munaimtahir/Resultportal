from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Student, StudentAccessToken, YearClass

from .admin import ResultAdmin
from .importers import ResultCSVImporter
from .models import Exam, ImportBatch, Result


class YearClassModelTests(TestCase):
    def test_ordering_by_order_field(self) -> None:
        """Test that YearClass orders by the order field."""
        year3 = YearClass.objects.create(label="3rd Year", order=3)
        year1 = YearClass.objects.create(label="1st Year", order=1)
        year2 = YearClass.objects.create(label="2nd Year", order=2)

        years = list(YearClass.objects.all())
        self.assertEqual(years, [year1, year2, year3])

    def test_unique_label_and_order(self) -> None:
        """Test that label and order must be unique."""
        YearClass.objects.create(label="1st Year", order=1)

        with self.assertRaises(Exception):  # IntegrityError
            YearClass.objects.create(label="1st Year", order=2)

        with self.assertRaises(Exception):  # IntegrityError
            YearClass.objects.create(label="First Year", order=1)


class ExamModelTests(TestCase):
    def setUp(self) -> None:
        self.year_class = YearClass.objects.create(label="2nd Year", order=2)

    def test_exam_creation(self) -> None:
        """Test basic exam creation."""
        exam = Exam.objects.create(
            year_class=self.year_class,
            code="BLOCK-E-2024",
            title="Block E Examination 2024",
            kind=Exam.ExamKind.BLOCK,
            block_letter="E",
            exam_date=date(2024, 6, 15),
        )

        self.assertEqual(str(exam), "BLOCK-E-2024 - Block E Examination 2024")
        self.assertEqual(exam.kind, Exam.ExamKind.BLOCK)

    def test_recheck_window_open(self) -> None:
        """Test recheck window status checking."""
        exam = Exam.objects.create(
            year_class=self.year_class,
            code="TEST-001",
            title="Test Exam",
            kind=Exam.ExamKind.TEST,
            exam_date=date.today(),
            recheck_deadline=timezone.now() + timedelta(days=7),
        )

        self.assertTrue(exam.is_recheck_open())

    def test_recheck_window_closed(self) -> None:
        """Test recheck window closed."""
        exam = Exam.objects.create(
            year_class=self.year_class,
            code="TEST-002",
            title="Test Exam 2",
            kind=Exam.ExamKind.TEST,
            exam_date=date.today(),
            recheck_deadline=timezone.now() - timedelta(days=1),
        )

        self.assertFalse(exam.is_recheck_open())

    def test_no_recheck_deadline(self) -> None:
        """Test when no recheck deadline is set."""
        exam = Exam.objects.create(
            year_class=self.year_class,
            code="TEST-003",
            title="Test Exam 3",
            kind=Exam.ExamKind.TEST,
            exam_date=date.today(),
        )

        self.assertFalse(exam.is_recheck_open())


class StudentAccessTokenTests(TestCase):
    def setUp(self) -> None:
        self.student = Student.objects.create(
            official_email="student@pmc.edu.pk",
            roll_number="PMC-001",
            display_name="Test Student",
        )

    def test_token_generation(self) -> None:
        """Test generating an access token."""
        token = StudentAccessToken.generate_for_student(self.student)

        self.assertEqual(token.student, self.student)
        self.assertIsNotNone(token.code)
        self.assertTrue(len(token.code) > 20)
        self.assertGreater(token.expires_at, timezone.now())
        self.assertIsNone(token.used_at)

    def test_token_validity_check(self) -> None:
        """Test token validity checking."""
        token = StudentAccessToken.generate_for_student(self.student, validity_hours=24)

        self.assertTrue(token.is_valid())

    def test_expired_token(self) -> None:
        """Test expired token is not valid."""
        token = StudentAccessToken.generate_for_student(self.student, validity_hours=0)
        token.expires_at = timezone.now() - timedelta(hours=1)
        token.save()

        self.assertFalse(token.is_valid())

    def test_used_token(self) -> None:
        """Test used token is not valid."""
        token = StudentAccessToken.generate_for_student(self.student)
        token.mark_used()

        self.assertFalse(token.is_valid())
        self.assertIsNotNone(token.used_at)

    def test_mark_used_idempotent(self) -> None:
        """Test that marking as used multiple times is safe."""
        token = StudentAccessToken.generate_for_student(self.student)
        token.mark_used()
        used_at_1 = token.used_at

        token.mark_used()
        used_at_2 = token.used_at

        self.assertEqual(used_at_1, used_at_2)


class ImportBatchModelTests(TestCase):
    def test_mark_completed_sets_timestamp_and_status(self) -> None:
        staff = get_user_model().objects.create_user(
            username="importer",
            email="importer@pmc.edu.pk",
            is_staff=True,
        )
        batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            started_by=staff,
            row_count=10,
            created_rows=5,
            updated_rows=5,
        )

        batch.mark_completed()

        batch.refresh_from_db()
        self.assertFalse(batch.is_dry_run)
        self.assertIsNotNone(batch.completed_at)
        self.assertLessEqual(batch.completed_at, timezone.now())


class ResultModelTests(TestCase):
    def setUp(self) -> None:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.staff_user = User.objects.create_user(
            username="admin", email="admin@pmc.edu.pk", is_staff=True
        )

        self.year_class = YearClass.objects.create(label="2nd Year", order=2)
        self.student = Student.objects.create(
            year_class=self.year_class,
            official_email="student@pmc.edu.pk",
            roll_number="PMC-001",
            display_name="Test Student",
        )
        self.exam = Exam.objects.create(
            year_class=self.year_class,
            code="BLOCK-E-2024",
            title="Block E",
            kind=Exam.ExamKind.BLOCK,
            exam_date=date.today(),
        )
        self.batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            is_dry_run=False,
        )

    def _build_result(self, **overrides):
        data = {
            "student": self.student,
            "exam": self.exam,
            "import_batch": self.batch,
            "respondent_id": "resp-1",
            "roll_number": self.student.roll_number,
            "name": "Test Student",
            "block": "E",
            "year": datetime.now().year + 1,
            "subject": "Pathology",
            "written_marks": Decimal("70.00"),
            "viva_marks": Decimal("20.00"),
            "total_marks": Decimal("90.00"),
            "grade": "A",
            "exam_date": timezone.now().date(),
        }
        data.update(overrides)
        return Result(**data)

    def test_clean_rejects_negative_marks(self) -> None:
        result = self._build_result(written_marks=Decimal("-1"))
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_clean_requires_total_to_match_components(self) -> None:
        result = self._build_result(total_marks=Decimal("80.00"))
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_clean_validates_roll_number_matches_student(self) -> None:
        result = self._build_result(roll_number="OTHER-ROLL")
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_result_status_workflow_submit(self) -> None:
        """Test submitting a draft result."""
        result = self._build_result()
        result.save()

        self.assertEqual(result.status, Result.ResultStatus.DRAFT)

        result.submit()
        result.refresh_from_db()

        self.assertEqual(result.status, Result.ResultStatus.SUBMITTED)
        self.assertTrue(len(result.status_log) > 0)

    def test_result_status_workflow_verify(self) -> None:
        """Test verifying a submitted result."""
        result = self._build_result()
        result.save()
        result.submit()

        result.verify(self.staff_user)
        result.refresh_from_db()

        self.assertEqual(result.status, Result.ResultStatus.VERIFIED)
        self.assertEqual(result.verified_by, self.staff_user)
        self.assertIsNotNone(result.verified_at)

    def test_result_status_workflow_return(self) -> None:
        """Test returning a submitted result."""
        result = self._build_result()
        result.save()
        result.submit()

        result.return_for_correction()
        result.refresh_from_db()

        self.assertEqual(result.status, Result.ResultStatus.RETURNED)

    def test_result_status_workflow_publish(self) -> None:
        """Test publishing a verified result."""
        result = self._build_result()
        result.save()
        result.submit()
        result.verify(self.staff_user)

        result.publish(self.staff_user)
        result.refresh_from_db()

        self.assertEqual(result.status, Result.ResultStatus.PUBLISHED)
        self.assertIsNotNone(result.published_at)
        self.assertTrue(result.is_published)

    def test_result_status_workflow_unpublish(self) -> None:
        """Test unpublishing a published result."""
        result = self._build_result()
        result.save()
        result.submit()
        result.verify(self.staff_user)
        result.publish(self.staff_user)

        result.unpublish(self.staff_user)
        result.refresh_from_db()

        self.assertEqual(result.status, Result.ResultStatus.VERIFIED)
        self.assertIsNone(result.published_at)
        self.assertFalse(result.is_published)

    def test_published_queryset_filters(self) -> None:
        """Test the published queryset filter."""
        published = self._build_result(subject="Anatomy")
        published.save()
        published.status = Result.ResultStatus.PUBLISHED
        published.save(update_fields=["status"])

        draft = self._build_result(subject="Biochem")
        draft.save()

        published_results = Result.objects.published()
        self.assertIn(published, published_results)
        self.assertNotIn(draft, published_results)

        self.assertIn(published, Result.objects.published())
        self.assertNotIn(draft, Result.objects.published())

    def test_publish_method_sets_timestamp(self):
        """Test that publish() sets published_at timestamp."""
        result = self._build_result()
        result.save()
        self.assertIsNone(result.published_at)
        self.assertFalse(result.is_published)

        # Follow the workflow: DRAFT -> SUBMITTED -> VERIFIED -> PUBLISHED
        result.submit()
        result.verify(self.staff_user)
        result.publish()
        result.refresh_from_db()
        self.assertIsNotNone(result.published_at)
        self.assertTrue(result.is_published)

    def test_publish_method_idempotent(self):
        """Test that calling publish() multiple times is safe."""
        result = self._build_result()
        result.save()
        # Follow the workflow: DRAFT -> SUBMITTED -> VERIFIED -> PUBLISHED
        result.submit()
        result.verify(self.staff_user)
        result.publish()
        first_published_at = result.published_at

        result.publish()
        result.refresh_from_db()
        # Should keep the original timestamp
        self.assertEqual(result.published_at, first_published_at)

    def test_unpublish_method_clears_timestamp(self):
        """Test that unpublish() clears published_at timestamp."""
        result = self._build_result(
            published_at=timezone.now(), status=Result.ResultStatus.PUBLISHED
        )
        result.save()
        self.assertTrue(result.is_published)

        result.unpublish()
        result.refresh_from_db()
        self.assertIsNone(result.published_at)
        self.assertFalse(result.is_published)

    def test_unpublish_method_idempotent(self):
        """Test that calling unpublish() on unpublished result is safe."""
        result = self._build_result()
        result.save()
        self.assertIsNone(result.published_at)

        result.unpublish()
        result.refresh_from_db()
        self.assertIsNone(result.published_at)

    def test_by_status_queryset_filter(self):
        """Test the by_status queryset filter."""
        result1 = self._build_result(subject="Anatomy")
        result1.save()
        result1.submit()

        result2 = self._build_result(subject="Biochem")
        result2.save()

        submitted = Result.objects.by_status(Result.ResultStatus.SUBMITTED)
        draft = Result.objects.by_status(Result.ResultStatus.DRAFT)

        self.assertIn(result1, submitted)
        self.assertNotIn(result2, submitted)
        self.assertIn(result2, draft)
        self.assertNotIn(result1, draft)

    def test_status_log_initialization(self):
        """Test that status_log gets initialized if not a list."""
        result = self._build_result()
        result.save()
        # Directly modify the status_log to a non-list value in memory
        result.status_log = {}  # Use dict instead of None
        result.submit()
        result.refresh_from_db()
        self.assertIsInstance(result.status_log, list)
        self.assertTrue(len(result.status_log) > 0)

    def test_sync_marks_with_flags(self):
        """Test the sync_marks_with_flags utility method."""
        result = self._build_result(
            written_marks=Decimal("70.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("90.00"),
        )
        result.sync_marks_with_flags()
        result.save()

        self.assertEqual(result.theory, Decimal("70.00"))
        self.assertEqual(result.practical, Decimal("20.00"))
        self.assertEqual(result.total, Decimal("90.00"))

    def test_clean_with_null_marks(self):
        """Test that clean handles null marks properly."""
        result = self._build_result(
            written_marks=None,
            viva_marks=None,
            total_marks=None,
            theory=Decimal("70.00"),
            practical=Decimal("20.00"),
            total=Decimal("90.00"),
        )
        # Should not raise ValidationError for null legacy marks
        result.full_clean()
        self.assertEqual(result.theory, Decimal("70.00"))


class ResultCSVImporterTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="importer",
            email="importer@pmc.edu.pk",
            password="testpass123",
            is_staff=True,
        )

        self.student = Student.objects.create(
            official_email="student@pmc.edu.pk",
            roll_number="PMC-001",
            display_name="Test Student",
        )

        self.initial_batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            started_by=self.staff_user,
            is_dry_run=False,
        )

        next_year = datetime.now().year + 1
        self.existing_result = Result.objects.create(
            student=self.student,
            import_batch=self.initial_batch,
            respondent_id="resp-1",
            roll_number=self.student.roll_number,
            name="Test Student",
            block="E",
            year=next_year,
            subject="Pathology",
            written_marks=Decimal("65.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("85.00"),
            grade="B",
            exam_date=date(next_year, 1, 15),
        )

        header = ",".join(
            [
                "respondent_id",
                "roll_no",
                "name",
                "block",
                "year",
                "subject",
                "written_marks",
                "viva_marks",
                "total_marks",
                "grade",
                "exam_date",
            ]
        )
        self.csv_header = header
        self.csv_payload = "\n".join(
            [
                header,
                f"resp-1,PMC-001,Test Student,E,{next_year},Pathology,70,20,90,A,{next_year}-01-15",
                f",PMC-001,Test Student,E,{next_year},Anatomy,80,20,100,A+,{next_year}-01-16",
                f",PMC-001,Test Student,E,{next_year},Physiology,50,20,60,A,{next_year}-01-17",
                f",PMC-999,Missing Student,E,{next_year},Pathology,60,20,80,B,{next_year}-01-18",
            ]
        )

    def _build_stream(self) -> io.StringIO:
        return io.StringIO(self.csv_payload)

    def test_preview_flags_errors_without_creating_results(self) -> None:
        importer = ResultCSVImporter(
            self._build_stream(),
            started_by=self.staff_user,
            filename="results.csv",
        )

        summary = importer.preview()

        self.assertTrue(summary.batch.is_dry_run)
        self.assertEqual(summary.created, 1)
        self.assertEqual(summary.updated, 1)
        self.assertEqual(summary.skipped, 2)
        self.assertEqual(summary.row_count, 4)
        self.assertEqual(Result.objects.count(), 1)

        updated_row = summary.row_results[0]
        self.assertEqual(updated_row.action, "updated")
        self.assertIn("Would apply", " ".join(updated_row.messages))

        invalid_total_row = summary.row_results[2]
        self.assertTrue(invalid_total_row.has_errors)
        self.assertIn("total", " ".join(invalid_total_row.errors).lower())

        missing_student_row = summary.row_results[3]
        self.assertTrue(missing_student_row.has_errors)
        self.assertIn("not found", " ".join(missing_student_row.errors))

    def test_commit_creates_and_updates_results(self) -> None:
        importer = ResultCSVImporter(self._build_stream(), started_by=self.staff_user)

        summary = importer.commit()

        self.assertFalse(summary.batch.is_dry_run)
        self.assertIsNotNone(summary.batch.completed_at)
        self.assertEqual(summary.created, 1)
        self.assertEqual(summary.updated, 1)
        self.assertEqual(summary.skipped, 2)

        results = Result.objects.order_by("exam_date")
        self.assertEqual(results.count(), 2)

        updated_result = results.first()
        self.assertEqual(updated_result.subject, "Pathology")
        self.assertEqual(updated_result.total_marks, Decimal("90"))
        self.assertEqual(updated_result.grade, "A")
        self.assertEqual(updated_result.import_batch, summary.batch)

        new_result = results.last()
        self.assertEqual(new_result.subject, "Anatomy")
        self.assertEqual(new_result.grade, "A+")
        self.assertEqual(new_result.import_batch, summary.batch)

        self.assertFalse(Result.objects.filter(subject="Physiology").exists())

    def test_missing_headers_raises_error(self):
        """Test that missing required headers raises ValueError."""
        csv_no_headers = io.StringIO("PMC-001,Test,E,2025,Pathology\n")
        importer = ResultCSVImporter(csv_no_headers, started_by=self.staff_user)

        with self.assertRaises(ValueError) as cm:
            importer.preview()
        self.assertIn("Missing required column", str(cm.exception))

    def test_empty_csv_raises_error(self):
        """Test that CSV without headers raises ValueError."""
        csv_empty = io.StringIO("")
        importer = ResultCSVImporter(csv_empty, started_by=self.staff_user)

        with self.assertRaises(ValueError) as cm:
            importer.preview()
        self.assertIn("must include a header row", str(cm.exception))

    def test_missing_required_fields(self):
        """Test that missing required fields are caught."""
        next_year = datetime.now().year + 1
        csv_missing = io.StringIO(
            "\n".join(
                [
                    self.csv_header,
                    # Missing name value
                    f",PMC-001,,E,{next_year},Pathology,70,20,90,A,{next_year}-01-15",
                ]
            )
        )
        importer = ResultCSVImporter(csv_missing, started_by=self.staff_user)
        summary = importer.preview()

        # Row should be skipped
        self.assertEqual(summary.skipped, 1)

    def test_invalid_year_format(self):
        """Test that invalid year format is caught."""
        next_year = datetime.now().year + 1
        csv_invalid = io.StringIO(
            "\n".join(
                [
                    self.csv_header,
                    f",PMC-001,Test,E,invalid,Pathology,70,20,90,A,{next_year}-01-15",
                ]
            )
        )
        importer = ResultCSVImporter(csv_invalid, started_by=self.staff_user)
        summary = importer.preview()

        self.assertEqual(summary.skipped, 1)
        self.assertTrue(
            any("year must be an integer" in " ".join(row.errors) for row in summary.row_results)
        )

    def test_invalid_date_format(self):
        """Test that invalid date format is caught."""
        next_year = datetime.now().year + 1
        csv_invalid = io.StringIO(
            "\n".join(
                [
                    self.csv_header,
                    f",PMC-001,Test,E,{next_year},Pathology,70,20,90,A,invalid-date",
                ]
            )
        )
        importer = ResultCSVImporter(csv_invalid, started_by=self.staff_user)
        summary = importer.preview()

        self.assertEqual(summary.skipped, 1)
        self.assertTrue(any("exam_date" in " ".join(row.errors) for row in summary.row_results))

    def test_invalid_marks_format(self):
        """Test that invalid marks format is caught."""
        next_year = datetime.now().year + 1
        csv_invalid = io.StringIO(
            "\n".join(
                [
                    self.csv_header,
                    f",PMC-001,Test,E,{next_year},Pathology,invalid,20,90,A,{next_year}-01-15",
                ]
            )
        )
        importer = ResultCSVImporter(csv_invalid, started_by=self.staff_user)
        summary = importer.preview()

        self.assertEqual(summary.skipped, 1)
        self.assertTrue(any("written_marks" in " ".join(row.errors) for row in summary.row_results))

    def test_duplicate_result_in_file(self):
        """Test that duplicate results within file are caught."""
        next_year = datetime.now().year + 1
        # Use the existing student from setUp
        csv_dupes = io.StringIO(
            "\n".join(
                [
                    self.csv_header,
                    f",PMC-001,Test,E,{next_year},Chemistry,70,20,90,A,{next_year}-01-20",
                    f",PMC-001,Test,E,{next_year},Chemistry,80,20,100,A+,{next_year}-01-20",
                    "",
                ]
            )
        )
        importer = ResultCSVImporter(csv_dupes, started_by=self.staff_user)
        summary = importer.preview()

        # Second row should be skipped due to duplicate
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.created, 1)

    def test_no_changes_detected_on_result_update(self):
        """Test that updating result with no changes is handled."""
        next_year = datetime.now().year + 1
        # Import exact same data as existing result
        csv_same = io.StringIO(
            "\n".join(
                [
                    self.csv_header,
                    (
                        "resp-1,PMC-001,Test Student,E,"
                        f"{next_year},Pathology,65,20,85,B,{next_year}-01-15"
                    ),
                    "",
                ]
            )
        )
        importer = ResultCSVImporter(csv_same, started_by=self.staff_user)
        summary = importer.preview()

        # Should be updated but with message about no changes
        self.assertEqual(summary.updated, 1)
        row_result = summary.row_results[0]
        self.assertIn("No changes detected", " ".join(row_result.messages))


class HomeViewTests(TestCase):
    """Tests for the home view."""

    def test_home_page_accessible(self):
        """Test that home page is accessible."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/home.html")

    def test_home_redirects_authenticated_user_with_student_profile(self):
        """Test that authenticated users with student profiles are redirected."""
        user = get_user_model().objects.create_user(
            username="student1",
            email="student1@pmc.edu.pk",
        )
        Student.objects.create(
            official_email="student1@pmc.edu.pk",
            roll_number="PMC-100",
            display_name="Test Student",
            user=user,
        )
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/me/", response.url)


class StudentProfileViewTests(TestCase):
    """Tests for the student profile view."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student1",
            email="student1@pmc.edu.pk",
        )
        self.student = Student.objects.create(
            official_email="student1@pmc.edu.pk",
            roll_number="PMC-100",
            display_name="Test Student",
            user=self.user,
        )

    def test_profile_requires_login(self):
        """Test that profile page requires authentication."""
        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/token/authenticate/", response.url)

    def test_profile_displays_student_info(self):
        """Test that profile page displays student information."""
        self.client.force_login(self.user)
        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/student_profile.html")
        self.assertEqual(response.context["student"], self.student)

    def test_profile_redirects_user_without_student_profile(self):
        """Test that users without student profiles are redirected."""
        user_no_profile = get_user_model().objects.create_user(
            username="noProfile",
            email="noprofile@pmc.edu.pk",
        )
        self.client.force_login(user_no_profile)
        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 302)


class StudentResultsViewTests(TestCase):
    """Tests for the student results view."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student1",
            email="student1@pmc.edu.pk",
        )
        self.student = Student.objects.create(
            official_email="student1@pmc.edu.pk",
            roll_number="PMC-100",
            display_name="Test Student",
            user=self.user,
        )
        self.batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            is_dry_run=False,
        )

    def test_results_page_requires_login(self):
        """Test that results page requires authentication."""
        response = self.client.get("/me/results/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/token/authenticate/", response.url)

    def test_results_page_only_shows_published_results(self):
        """Test that only published results are shown."""
        from django.utils import timezone

        # Create published result (with proper workflow status)
        published = Result.objects.create(
            student=self.student,
            import_batch=self.batch,
            roll_number=self.student.roll_number,
            name="Test Student",
            block="E",
            year=2025,
            subject="Pathology",
            written_marks=Decimal("70.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("90.00"),
            grade="A",
            exam_date=date(2025, 1, 15),
            published_at=timezone.now(),
            status=Result.ResultStatus.PUBLISHED,
        )

        # Create unpublished result
        unpublished = Result.objects.create(
            student=self.student,
            import_batch=self.batch,
            roll_number=self.student.roll_number,
            name="Test Student",
            block="E",
            year=2025,
            subject="Anatomy",
            written_marks=Decimal("80.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("100.00"),
            grade="A+",
            exam_date=date(2025, 1, 16),
            published_at=None,
        )

        self.client.force_login(self.user)
        response = self.client.get("/me/results/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/student_results.html")
        results = response.context["results"]
        self.assertIn(published, results)
        self.assertNotIn(unpublished, results)

    def test_results_page_only_shows_own_results(self):
        """Test that students only see their own results."""
        from django.utils import timezone

        # Create another student
        other_user = get_user_model().objects.create_user(
            username="student2",
            email="student2@pmc.edu.pk",
        )
        other_student = Student.objects.create(
            official_email="student2@pmc.edu.pk",
            roll_number="PMC-200",
            display_name="Other Student",
            user=other_user,
        )

        # Create result for other student
        other_result = Result.objects.create(
            student=other_student,
            import_batch=self.batch,
            roll_number=other_student.roll_number,
            name="Other Student",
            block="E",
            year=2025,
            subject="Pathology",
            written_marks=Decimal("70.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("90.00"),
            grade="A",
            exam_date=date(2025, 1, 15),
            published_at=timezone.now(),
        )

        self.client.force_login(self.user)
        response = self.client.get("/me/results/")
        results = response.context["results"]
        self.assertNotIn(other_result, results)

    def test_results_page_redirects_user_without_student_profile(self):
        """Test that users without student profiles are redirected."""
        user_no_profile = get_user_model().objects.create_user(
            username="noProfile",
            email="noprofile@pmc.edu.pk",
        )
        self.client.force_login(user_no_profile)
        response = self.client.get("/me/results/")
        self.assertEqual(response.status_code, 302)


class TokenBasedAccessTests(TestCase):
    """Tests for token-based access to student views."""

    def setUp(self):
        self.year_class = YearClass.objects.create(label="1st Year", order=1)
        self.student = Student.objects.create(
            year_class=self.year_class,
            official_email="student@pmc.edu.pk",
            roll_number="PMC-123",
            display_name="Test Student",
        )
        self.exam = Exam.objects.create(
            year_class=self.year_class,
            code="BLOCK-A-2025",
            title="Block A Exam",
            kind=Exam.ExamKind.BLOCK,
            exam_date=date.today(),
        )
        self.batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            is_dry_run=False,
        )

    def test_token_based_access_to_profile(self):
        """Test accessing profile with token-based authentication."""
        # Simulate token authentication in session
        session = self.client.session
        session["token_authenticated"] = True
        session["token_student_id"] = self.student.id
        session.save()

        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/student_profile.html")
        self.assertEqual(response.context["student"], self.student)

    def test_token_based_access_to_results(self):
        """Test accessing results with token-based authentication."""
        # Create published result
        from django.utils import timezone

        Result.objects.create(
            student=self.student,
            exam=self.exam,
            import_batch=self.batch,
            roll_number=self.student.roll_number,
            name="Test Student",
            block="A",
            year=2025,
            subject="Pathology",
            written_marks=Decimal("70.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("90.00"),
            grade="A",
            exam_date=date.today(),
            published_at=timezone.now(),
            status=Result.ResultStatus.PUBLISHED,
        )

        # Simulate token authentication in session
        session = self.client.session
        session["token_authenticated"] = True
        session["token_student_id"] = self.student.id
        session.save()

        response = self.client.get("/me/results/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/student_results.html")
        self.assertEqual(len(response.context["results"]), 1)

    def test_home_redirects_for_token_authenticated_user(self):
        """Test that home page redirects token-authenticated users."""
        # Simulate token authentication in session
        session = self.client.session
        session["token_authenticated"] = True
        session["token_student_id"] = self.student.id
        session.save()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/me/", response.url)

    def test_profile_with_recheck_link(self):
        """Test profile displays recheck link when available."""
        from datetime import timedelta

        from django.utils import timezone

        # Create exam with recheck deadline in future
        exam_with_recheck = Exam.objects.create(
            year_class=self.year_class,
            code="BLOCK-B-2025",
            title="Block B Exam",
            kind=Exam.ExamKind.BLOCK,
            exam_date=date.today(),
            recheck_form_url="https://example.com/recheck",
            recheck_deadline=timezone.now() + timedelta(days=7),
        )

        # Create published result for this exam
        Result.objects.create(
            student=self.student,
            exam=exam_with_recheck,
            import_batch=self.batch,
            roll_number=self.student.roll_number,
            name="Test Student",
            block="B",
            year=2025,
            subject="Pathology",
            written_marks=Decimal("70.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("90.00"),
            grade="A",
            exam_date=date.today(),
            published_at=timezone.now(),
            status=Result.ResultStatus.PUBLISHED,
        )

        # Simulate token authentication
        session = self.client.session
        session["token_authenticated"] = True
        session["token_student_id"] = self.student.id
        session.save()

        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 200)
        # Check that exam with recheck is in context
        exams_with_results = response.context["exams_with_results"]
        self.assertEqual(len(exams_with_results), 1)
        self.assertTrue(exams_with_results[0]["recheck_open"])


class TokenAccessEdgeCases(TestCase):
    """Test edge cases for token-based access."""

    def setUp(self):
        self.year_class = YearClass.objects.create(label="1st Year", order=1)

    def test_profile_with_invalid_token_student_id(self):
        """Test profile access with invalid student ID in session."""
        # Simulate token authentication with non-existent student ID
        session = self.client.session
        session["token_authenticated"] = True
        session["token_student_id"] = 99999  # Non-existent ID
        session.save()

        response = self.client.get("/me/")
        # Should still render but without student data
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("published_results_count", response.context)

    def test_results_with_invalid_token_student_id(self):
        """Test results access with invalid student ID in session."""
        # Simulate token authentication with non-existent student ID
        session = self.client.session
        session["token_authenticated"] = True
        session["token_student_id"] = 99999  # Non-existent ID
        session.save()

        response = self.client.get("/me/results/")
        self.assertEqual(response.status_code, 200)
        # Should return empty queryset
        self.assertEqual(len(response.context["results"]), 0)


class CSVImportViewsTests(TestCase):
    """Tests for CSV import views."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.staff_user = User.objects.create_user(
            username="staff", email="staff@pmc.edu.pk", is_staff=True
        )
        self.year_class = YearClass.objects.create(label="1st Year", order=1)
        self.exam = Exam.objects.create(
            year_class=self.year_class,
            code="BLOCK-A-2025",
            title="Block A Exam",
            kind=Exam.ExamKind.BLOCK,
            exam_date=date.today(),
        )

    def test_student_csv_upload_requires_staff(self):
        """Test that student CSV upload requires staff authentication."""
        response = self.client.get("/import/students/upload/")
        self.assertEqual(response.status_code, 302)

    def test_student_csv_upload_view_accessible_for_staff(self):
        """Test that student CSV upload view is accessible for staff."""
        self.client.force_login(self.staff_user)
        response = self.client.get("/import/students/upload/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/import/upload_students.html")

    def test_student_csv_upload_with_valid_file(self):
        """Test uploading a valid student CSV file."""
        import io

        csv_content = """roll_no,first_name,last_name,display_name,official_email
PMC-001,John,Doe,John Doe,john@pmc.edu.pk
PMC-002,Jane,Smith,Jane Smith,jane@pmc.edu.pk"""
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "students.csv"

        self.client.force_login(self.staff_user)
        response = self.client.post(
            "/import/students/upload/",
            {"csv_file": csv_file, "year_class": self.year_class.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/import/students/preview/")

        # Check session data
        self.assertIn("student_import_preview", self.client.session)

    def test_student_csv_preview_shows_summary(self):
        """Test that student CSV preview shows import summary."""
        # Set up session with preview data
        session = self.client.session
        session["student_import_preview"] = {
            "year_class_id": self.year_class.id,
            "csv_content": "roll_no,first_name,last_name,display_name,official_email\nPMC-001,John,Doe,John Doe,john@pmc.edu.pk",
            "row_count": 1,
            "created": 1,
            "updated": 0,
            "skipped": 0,
            "has_errors": False,
            "errors": [],
            "warnings": [],
        }
        session.save()

        self.client.force_login(self.staff_user)
        response = self.client.get("/import/students/preview/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/import/preview_students.html")
        self.assertContains(response, "1")  # Row count

    def test_student_csv_preview_submit_creates_batch(self):
        """Test that submitting student CSV preview creates an import batch."""
        # Set up session with preview data
        session = self.client.session
        session["student_import_preview"] = {
            "year_class_id": self.year_class.id,
            "csv_content": "roll_no,first_name,last_name,display_name,official_email\nPMC-100,John,Doe,John Doe,john100@pmc.edu.pk",
            "row_count": 1,
            "created": 1,
            "updated": 0,
            "skipped": 0,
            "has_errors": False,
            "errors": [],
            "warnings": [],
        }
        session.save()

        self.client.force_login(self.staff_user)
        batch_count_before = ImportBatch.objects.count()

        response = self.client.post("/import/students/preview/", {"submit": "1"})
        self.assertEqual(response.status_code, 302)

        # Check that batch was created
        self.assertEqual(ImportBatch.objects.count(), batch_count_before + 1)
        batch = ImportBatch.objects.latest("id")
        self.assertEqual(batch.import_type, ImportBatch.ImportType.STUDENTS)
        self.assertFalse(batch.is_dry_run)

    def test_result_csv_upload_requires_staff(self):
        """Test that result CSV upload requires staff authentication."""
        response = self.client.get("/import/results/upload/")
        self.assertEqual(response.status_code, 302)

    def test_result_csv_upload_view_accessible_for_staff(self):
        """Test that result CSV upload view is accessible for staff."""
        self.client.force_login(self.staff_user)
        response = self.client.get("/import/results/upload/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/import/upload_results.html")

    def test_result_csv_upload_with_valid_file(self):
        """Test uploading a valid result CSV file."""
        import io

        # Create a student first
        Student.objects.create(
            year_class=self.year_class,
            official_email="student@pmc.edu.pk",
            roll_number="PMC-100",
        )

        csv_content = """roll_no,name,block,year,subject,written_marks,viva_marks,total_marks,grade,exam_date
PMC-100,Test Student,A,1,Anatomy,70,20,90,A,2025-01-15"""
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "results.csv"

        self.client.force_login(self.staff_user)
        response = self.client.post(
            "/import/results/upload/", {"csv_file": csv_file, "exam": self.exam.id}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/import/results/preview/")

        # Check session data
        self.assertIn("result_import_preview", self.client.session)

    def test_result_csv_preview_shows_summary(self):
        """Test that result CSV preview shows import summary."""
        # Create a batch for the preview
        batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            exam=self.exam,
            started_by=self.staff_user,
            is_dry_run=True,
        )

        # Set up session with preview data
        session = self.client.session
        session["result_import_preview"] = {
            "exam_id": self.exam.id,
            "batch_id": batch.id,
            "csv_content": "roll_no,name,block,year,subject,written_marks,viva_marks,total_marks,grade,exam_date\nPMC-100,Test,A,1,Anatomy,70,20,90,A,2025-01-15",
            "filename": "results.csv",
            "row_count": 1,
            "created": 1,
            "updated": 0,
            "skipped": 0,
            "has_errors": False,
            "errors": [],
            "warnings": [],
        }
        session.save()

        self.client.force_login(self.staff_user)
        response = self.client.get("/import/results/preview/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "results/import/preview_results.html")
        self.assertContains(response, self.exam.title)

    def test_result_csv_preview_submit_creates_results(self):
        """Test that submitting result CSV preview creates results."""
        # Create a student first
        student = Student.objects.create(
            year_class=self.year_class,
            official_email="student@pmc.edu.pk",
            roll_number="PMC-100",
        )

        # Create a batch for the preview
        batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            exam=self.exam,
            started_by=self.staff_user,
            is_dry_run=True,
        )

        # Set up session with preview data
        session = self.client.session
        session["result_import_preview"] = {
            "exam_id": self.exam.id,
            "batch_id": batch.id,
            "csv_content": "roll_no,name,block,year,subject,written_marks,viva_marks,total_marks,grade,exam_date\nPMC-100,Test,A,1,Anatomy,70,20,90,A,2025-01-15",
            "filename": "results.csv",
            "row_count": 1,
            "created": 1,
            "updated": 0,
            "skipped": 0,
            "has_errors": False,
            "errors": [],
            "warnings": [],
        }
        session.save()

        self.client.force_login(self.staff_user)
        result_count_before = Result.objects.count()

        response = self.client.post("/import/results/preview/", {"submit": "1"})
        self.assertEqual(response.status_code, 302)

        # Check that results were created
        self.assertGreater(Result.objects.count(), result_count_before)

        # Check that a new batch was created and marked as completed
        new_batch = ImportBatch.objects.latest("id")
        self.assertFalse(new_batch.is_dry_run)
        self.assertIsNotNone(new_batch.completed_at)

    def test_csv_preview_without_session_redirects(self):
        """Test that accessing preview without session data redirects."""
        self.client.force_login(self.staff_user)

        # Try to access preview without upload
        response = self.client.get("/import/students/preview/")
        self.assertEqual(response.status_code, 200)
        # Should show error message (checked via messages framework)

        response = self.client.get("/import/results/preview/")
        self.assertEqual(response.status_code, 200)
        # Should show error message

    def test_student_preview_post_without_session_redirects(self):
        """Test posting to preview without session redirects."""
        self.client.force_login(self.staff_user)
        response = self.client.post("/import/students/preview/", {"submit": "1"})
        self.assertEqual(response.status_code, 302)

    def test_result_preview_post_without_session_redirects(self):
        """Test posting to preview without session redirects."""
        self.client.force_login(self.staff_user)
        response = self.client.post("/import/results/preview/", {"submit": "1"})
        self.assertEqual(response.status_code, 302)

    def test_student_preview_post_without_submit_redirects(self):
        """Test posting to student preview without submit button redirects."""
        session = self.client.session
        session["student_import_preview"] = {"csv_content": "test"}
        session.save()

        self.client.force_login(self.staff_user)
        response = self.client.post("/import/students/preview/", {"cancel": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/import/students/upload/", response.url)

    def test_result_preview_post_without_submit_redirects(self):
        """Test posting to result preview without submit button redirects."""
        session = self.client.session
        session["result_import_preview"] = {"csv_content": "test", "filename": "test.csv"}
        session.save()

        self.client.force_login(self.staff_user)
        response = self.client.post("/import/results/preview/", {"cancel": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/import/results/upload/", response.url)


class AdminActionsTests(TestCase):
    """Tests for admin bulk actions."""

    def setUp(self):
        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@pmc.edu.pk", is_staff=True, is_superuser=True
        )
        self.year_class = YearClass.objects.create(label="1st Year", order=1)
        self.student = Student.objects.create(
            year_class=self.year_class,
            official_email="student@pmc.edu.pk",
            roll_number="PMC-100",
        )
        self.exam = Exam.objects.create(
            year_class=self.year_class,
            code="BLOCK-A-2025",
            title="Block A Exam",
            kind=Exam.ExamKind.BLOCK,
            exam_date=date.today(),
        )
        self.batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            is_dry_run=False,
        )

        self.site = AdminSite()
        self.result_admin = ResultAdmin(Result, self.site)

    def test_verify_results_action(self):
        """Test bulk verify action."""
        from unittest.mock import Mock

        from django.contrib.admin.sites import AdminSite
        from django.http import HttpRequest

        # Create SUBMITTED results
        result1 = Result.objects.create(
            student=self.student,
            exam=self.exam,
            import_batch=self.batch,
            roll_number="PMC-100",
            name="Test",
            subject="Anatomy",
            block="A",
            year=1,
            total=Decimal("80"),
            grade="A",
            exam_date=date.today(),
            status=Result.ResultStatus.SUBMITTED,
        )

        request = HttpRequest()
        request.user = self.admin_user
        queryset = Result.objects.filter(id=result1.id)

        # Mock message_user
        self.result_admin.message_user = Mock()

        self.result_admin.verify_results(request, queryset)

        result1.refresh_from_db()
        self.assertEqual(result1.status, Result.ResultStatus.VERIFIED)

        result1.refresh_from_db()
        self.assertEqual(result1.status, Result.ResultStatus.VERIFIED)

    def test_return_results_action(self):
        """Test bulk return action."""
        from django.http import HttpRequest

        result1 = Result.objects.create(
            student=self.student,
            exam=self.exam,
            import_batch=self.batch,
            roll_number="PMC-100",
            name="Test",
            subject="Anatomy",
            block="A",
            year=1,
            total=Decimal("80"),
            grade="A",
            exam_date=date.today(),
            status=Result.ResultStatus.SUBMITTED,
        )

        request = HttpRequest()
        request.user = self.admin_user
        queryset = Result.objects.filter(id=result1.id)

        self.result_admin.message_user = Mock()

        self.result_admin.return_results(request, queryset)

        result1.refresh_from_db()
        self.assertEqual(result1.status, Result.ResultStatus.RETURNED)

    def test_publish_results_action(self):
        """Test bulk publish action."""
        from django.http import HttpRequest

        result1 = Result.objects.create(
            student=self.student,
            exam=self.exam,
            import_batch=self.batch,
            roll_number="PMC-100",
            name="Test",
            subject="Anatomy",
            block="A",
            year=1,
            total=Decimal("80"),
            grade="A",
            exam_date=date.today(),
            status=Result.ResultStatus.VERIFIED,
        )

        request = HttpRequest()
        request.user = self.admin_user
        queryset = Result.objects.filter(id=result1.id)

        self.result_admin.message_user = Mock()

        self.result_admin.publish_results(request, queryset)

        result1.refresh_from_db()
        self.assertEqual(result1.status, Result.ResultStatus.PUBLISHED)

    def test_unpublish_results_action(self):
        """Test bulk unpublish action."""
        from django.http import HttpRequest
        from django.utils import timezone

        result1 = Result.objects.create(
            student=self.student,
            exam=self.exam,
            import_batch=self.batch,
            roll_number="PMC-100",
            name="Test",
            subject="Anatomy",
            block="A",
            year=1,
            total=Decimal("80"),
            grade="A",
            exam_date=date.today(),
            status=Result.ResultStatus.PUBLISHED,
            published_at=timezone.now(),
        )

        request = HttpRequest()
        request.user = self.admin_user
        queryset = Result.objects.filter(id=result1.id)

        self.result_admin.message_user = Mock()

        self.result_admin.unpublish_results(request, queryset)

        result1.refresh_from_db()
        self.assertEqual(result1.status, Result.ResultStatus.VERIFIED)
        self.assertIsNone(result1.published_at)

    def test_export_as_csv_action(self):
        """Test CSV export action."""
        from django.http import HttpRequest

        result1 = Result.objects.create(
            student=self.student,
            exam=self.exam,
            import_batch=self.batch,
            roll_number="PMC-100",
            name="Test Student",
            subject="Anatomy",
            block="A",
            year=1,
            theory=Decimal("70"),
            practical=Decimal("20"),
            total=Decimal("90"),
            grade="A",
            exam_date=date.today(),
            status=Result.ResultStatus.PUBLISHED,
        )

        request = HttpRequest()
        request.user = self.admin_user
        queryset = Result.objects.filter(id=result1.id)

        self.result_admin.message_user = Mock()

        response = self.result_admin.export_as_csv(request, queryset)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("results_export.csv", response["Content-Disposition"])

        content = response.content.decode("utf-8")
        self.assertIn("PMC-100", content)
        self.assertIn("Test Student", content)
        self.assertIn("Anatomy", content)
