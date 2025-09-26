import io
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Student

from .importers import ResultCSVImporter
from .models import ImportBatch, Result


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
        self.student = Student.objects.create(
            official_email="student@pmc.edu.pk",
            roll_number="PMC-001",
            display_name="Test Student",
        )
        self.batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            is_dry_run=False,
        )

    def _build_result(self, **overrides):
        data = {
            "student": self.student,
            "import_batch": self.batch,
            "respondent_id": "resp-1",
            "roll_number": self.student.roll_number,
            "name": "Test Student",
            "block": "E",
            "year": 2025,
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

    def test_published_queryset_filters(self) -> None:
        published = self._build_result(subject="Anatomy", published_at=timezone.now())
        published.save()
        draft = self._build_result(subject="Biochem", published_at=None)
        draft.save()

        qs = Result.objects.published()
        self.assertIn(published, qs)
        self.assertNotIn(draft, qs)


class ResultCSVImporterTests(TestCase):
    def setUp(self) -> None:
        self.student = Student.objects.create(
            roll_number="PMC-001",
            official_email="student@pmc.edu.pk",
            display_name="Test Student",
        )
        self.staff_user = get_user_model().objects.create_user(
            username="importer",
            email="importer@pmc.edu.pk",
            is_staff=True,
        )
        self.initial_batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            is_dry_run=False,
        )
        self.existing_result = Result.objects.create(
            student=self.student,
            import_batch=self.initial_batch,
            respondent_id="resp-1",
            roll_number="PMC-001",
            name="Test Student",
            block="E",
            year=2025,
            subject="Pathology",
            written_marks=Decimal("65.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("85.00"),
            grade="B",
            exam_date=date(2025, 1, 15),
        )

        self.csv_payload = """respondent_id,roll_no,name,block,year,subject,written_marks,viva_marks,total_marks,grade,exam_date
resp-1,PMC-001,Test Student,E,2025,Pathology,70,20,90,A,2025-01-15
,PMC-001,Test Student,E,2025,Anatomy,80,20,100,A+,2025-01-16
,PMC-001,Test Student,E,2025,Physiology,50,20,60,A,2025-01-17
,PMC-999,Missing Student,E,2025,Pathology,60,20,80,B,2025-01-18
"""

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
        self.assertIn("total_marks", " ".join(invalid_total_row.errors))

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


class StudentResultViewsTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="student",
            email="student@pmc.edu.pk",
        )
        self.student = Student.objects.create(
            user=self.user,
            official_email="student@pmc.edu.pk",
            roll_number="PMC-001",
            display_name="Test Student",
            status=Student.Status.ACTIVE,
        )
        self.batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS,
            is_dry_run=False,
        )
        self.published_result = Result.objects.create(
            student=self.student,
            import_batch=self.batch,
            respondent_id="resp-1",
            roll_number="PMC-001",
            name="Test Student",
            block="E",
            year=2025,
            subject="Pathology",
            written_marks=Decimal("75.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("95.00"),
            grade="A",
            exam_date=date(2025, 1, 15),
            published_at=timezone.now(),
        )
        self.draft_result = Result.objects.create(
            student=self.student,
            import_batch=self.batch,
            respondent_id="resp-2",
            roll_number="PMC-001",
            name="Test Student",
            block="E",
            year=2025,
            subject="Biochemistry",
            written_marks=Decimal("60.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("80.00"),
            grade="B",
            exam_date=date(2025, 1, 20),
        )

    def test_dashboard_requires_login(self) -> None:
        response = self.client.get(reverse("results:me"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.headers["Location"])

    def test_dashboard_blocks_unlinked_user(self) -> None:
        other_user = get_user_model().objects.create_user(
            username="orphan",
            email="orphan@pmc.edu.pk",
        )
        self.client.force_login(other_user)

        response = self.client.get(reverse("results:me"))

        self.assertEqual(response.status_code, 403)

    def test_dashboard_blocks_inactive_student(self) -> None:
        inactive_user = get_user_model().objects.create_user(
            username="inactive",
            email="inactive@pmc.edu.pk",
        )
        Student.objects.create(
            user=inactive_user,
            official_email="inactive@pmc.edu.pk",
            roll_number="PMC-999",
            display_name="Inactive Student",
            status=Student.Status.INACTIVE,
        )

        self.client.force_login(inactive_user)
        response = self.client.get(reverse("results:me"))

        self.assertEqual(response.status_code, 403)

    def test_dashboard_shows_only_published_results(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("results:me"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published results")
        self.assertContains(response, self.published_result.subject)
        self.assertNotContains(response, self.draft_result.subject)

    def test_results_list_filters_to_student_published_results(self) -> None:
        other_student = Student.objects.create(
            official_email="other@pmc.edu.pk",
            roll_number="PMC-777",
            display_name="Other Student",
            status=Student.Status.ACTIVE,
        )
        Result.objects.create(
            student=other_student,
            import_batch=self.batch,
            respondent_id="resp-3",
            roll_number="PMC-777",
            name="Other Student",
            block="E",
            year=2025,
            subject="Anatomy",
            written_marks=Decimal("70.00"),
            viva_marks=Decimal("20.00"),
            total_marks=Decimal("90.00"),
            grade="A",
            exam_date=date(2025, 2, 1),
            published_at=timezone.now(),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("results:me-results"))

        self.assertEqual(response.status_code, 200)
        results = list(response.context["results"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].subject, self.published_result.subject)
        self.assertNotContains(response, "Anatomy")
        self.assertContains(response, "1 result")
