from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Student, YearClass, StudentAccessToken

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
            recheck_deadline=timezone.now() + timedelta(days=7)
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
            recheck_deadline=timezone.now() - timedelta(days=1)
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
        first_used = timezone.now()
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
        user = get_user_model().objects.create_user(
            username="admin",
            email="admin@pmc.edu.pk",
        )
        result = self._build_result()
        result.save()
        result.submit()
        
        result.verify(user)
        result.refresh_from_db()
        
        self.assertEqual(result.status, Result.ResultStatus.VERIFIED)
        self.assertEqual(result.verified_by, user)
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
        user = get_user_model().objects.create_user(
            username="admin",
            email="admin@pmc.edu.pk",
        )
        result = self._build_result()
        result.save()
        result.submit()
        result.verify(user)
        
        result.publish(user)
        result.refresh_from_db()
        
        self.assertEqual(result.status, Result.ResultStatus.PUBLISHED)
        self.assertIsNotNone(result.published_at)
        self.assertTrue(result.is_published)
    
    def test_result_status_workflow_unpublish(self) -> None:
        """Test unpublishing a published result."""
        user = get_user_model().objects.create_user(
            username="admin",
            email="admin@pmc.edu.pk",
        )
        result = self._build_result()
        result.save()
        result.submit()
        result.verify(user)
        result.publish(user)
        
        result.unpublish(user)
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
