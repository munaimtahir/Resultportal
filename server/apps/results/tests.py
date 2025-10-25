from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
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

    def test_published_queryset_filters(self) -> None:
        published = self._build_result(subject="Anatomy", published_at=timezone.now())
        published.save()
        draft = self._build_result(subject="Biochem", published_at=None)
        draft.save()


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

        self.csv_payload = (
            "respondent_id,roll_no,name,block,year,subject,written_marks,viva_marks,total_marks,grade,exam_date\n"
            f"resp-1,PMC-001,Test Student,E,{next_year},Pathology,70,20,90,A,{next_year}-01-15\n"
            f",PMC-001,Test Student,E,{next_year},Anatomy,80,20,100,A+,{next_year}-01-16\n"
            f",PMC-001,Test Student,E,{next_year},Physiology,50,20,60,A,{next_year}-01-17\n"
            f",PMC-999,Missing Student,E,{next_year},Pathology,60,20,80,B,{next_year}-01-18"
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
