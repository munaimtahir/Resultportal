"""Tests for analytics app functionality."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Student, YearClass
from apps.results.models import Exam, ImportBatch, Result

from .models import AnomalyFlag, ComponentAggregate, ExamAggregate
from .services import (
    _calculate_median,
    compute_all_analytics,
    compute_component_aggregates,
    compute_exam_aggregates,
    detect_anomalies,
)

User = get_user_model()


class MedianCalculationTests(TestCase):
    """Tests for median calculation helper function."""

    def test_calculate_median_empty_list(self):
        """Test median calculation with empty list."""
        result = _calculate_median([])
        self.assertIsNone(result)

    def test_calculate_median_odd_count(self):
        """Test median calculation with odd number of values."""
        result = _calculate_median([Decimal("1"), Decimal("2"), Decimal("3")])
        self.assertEqual(result, Decimal("2"))

    def test_calculate_median_even_count(self):
        """Test median calculation with even number of values."""
        result = _calculate_median([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")])
        self.assertEqual(result, Decimal("2.5"))


class ExamAggregateComputationTests(TestCase):
    """Tests for exam aggregate computation."""

    def setUp(self):
        """Set up test data."""
        self.year_class = YearClass.objects.create(label="Year 1", order=1)
        self.exam = Exam.objects.create(
            year_class=self.year_class, code="TEST-001", title="Test Exam", exam_date="2024-01-15"
        )
        self.import_batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS, exam=self.exam
        )
        self.student1 = Student.objects.create(
            year_class=self.year_class, roll_number="001", official_email="student1@example.com"
        )
        self.student2 = Student.objects.create(
            year_class=self.year_class, roll_number="002", official_email="student2@example.com"
        )

    def test_compute_exam_aggregates_with_no_results(self):
        """Test computation when no results exist."""
        aggregate = compute_exam_aggregates(self.exam)

        self.assertEqual(aggregate.total_students, 0)
        self.assertIsNone(aggregate.mean_score)
        self.assertIsNone(aggregate.median_score)

    def test_compute_exam_aggregates_with_results(self):
        """Test computation with published results."""
        Result.objects.create(
            student=self.student1,
            exam=self.exam,
            import_batch=self.import_batch,
            roll_number="001",
            name="Student 1",
            block="A",
            year=2024,
            subject="Math",
            theory=Decimal("70.00"),
            practical=Decimal("30.00"),
            total=Decimal("100.00"),
            grade="A",
            exam_date="2024-01-15",
            status=Result.ResultStatus.PUBLISHED,
        )
        Result.objects.create(
            student=self.student2,
            exam=self.exam,
            import_batch=self.import_batch,
            roll_number="002",
            name="Student 2",
            block="A",
            year=2024,
            subject="Math",
            theory=Decimal("50.00"),
            practical=Decimal("30.00"),
            total=Decimal("80.00"),
            grade="B",
            exam_date="2024-01-15",
            status=Result.ResultStatus.PUBLISHED,
        )

        aggregate = compute_exam_aggregates(self.exam)

        self.assertEqual(aggregate.total_students, 2)
        self.assertEqual(aggregate.mean_score, Decimal("90.00"))
        self.assertEqual(aggregate.median_score, Decimal("90.00"))
        self.assertEqual(aggregate.min_score, Decimal("80.00"))
        self.assertEqual(aggregate.max_score, Decimal("100.00"))
        self.assertEqual(aggregate.pass_count, 2)
        self.assertEqual(aggregate.fail_count, 0)
        self.assertEqual(aggregate.pass_rate, Decimal("100.00"))
        self.assertEqual(aggregate.grade_a_count, 1)
        self.assertEqual(aggregate.grade_b_count, 1)

    def test_compute_exam_aggregates_ignores_unpublished_results(self):
        """Test that only published results are included."""
        Result.objects.create(
            student=self.student1,
            exam=self.exam,
            import_batch=self.import_batch,
            roll_number="001",
            name="Student 1",
            block="A",
            year=2024,
            subject="Math",
            total=Decimal("100.00"),
            grade="A",
            exam_date="2024-01-15",
            status=Result.ResultStatus.DRAFT,
        )

        aggregate = compute_exam_aggregates(self.exam)
        self.assertEqual(aggregate.total_students, 0)

    def test_compute_exam_aggregates_with_failing_grades(self):
        """Test pass rate calculation with failing grades."""
        Result.objects.create(
            student=self.student1,
            exam=self.exam,
            import_batch=self.import_batch,
            roll_number="001",
            name="Student 1",
            block="A",
            year=2024,
            subject="Math",
            total=Decimal("40.00"),
            grade="F",
            exam_date="2024-01-15",
            status=Result.ResultStatus.PUBLISHED,
        )
        Result.objects.create(
            student=self.student2,
            exam=self.exam,
            import_batch=self.import_batch,
            roll_number="002",
            name="Student 2",
            block="A",
            year=2024,
            subject="Math",
            total=Decimal("80.00"),
            grade="B",
            exam_date="2024-01-15",
            status=Result.ResultStatus.PUBLISHED,
        )

        aggregate = compute_exam_aggregates(self.exam)

        self.assertEqual(aggregate.pass_count, 1)
        self.assertEqual(aggregate.fail_count, 1)
        self.assertEqual(aggregate.pass_rate, Decimal("50.00"))


class ComponentAggregateComputationTests(TestCase):
    """Tests for component aggregate computation."""

    def setUp(self):
        """Set up test data."""
        self.year_class = YearClass.objects.create(label="Year 1", order=1)
        self.exam = Exam.objects.create(
            year_class=self.year_class, code="TEST-001", title="Test Exam", exam_date="2024-01-15"
        )
        self.import_batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS, exam=self.exam
        )
        self.student = Student.objects.create(
            year_class=self.year_class, roll_number="001", official_email="student@example.com"
        )

    def test_compute_component_aggregates(self):
        """Test component aggregate computation."""
        Result.objects.create(
            student=self.student,
            exam=self.exam,
            import_batch=self.import_batch,
            roll_number="001",
            name="Student",
            block="A",
            year=2024,
            subject="Math",
            theory=Decimal("70.00"),
            practical=Decimal("30.00"),
            total=Decimal("100.00"),
            grade="A",
            exam_date="2024-01-15",
            status=Result.ResultStatus.PUBLISHED,
        )

        aggregates = compute_component_aggregates(self.exam)

        self.assertEqual(len(aggregates), 3)  # Theory, Practical, Total

        theory_agg = next(
            (a for a in aggregates if a.component == ComponentAggregate.Component.THEORY), None
        )
        self.assertIsNotNone(theory_agg)
        self.assertEqual(theory_agg.mean_score, Decimal("70.00"))

        practical_agg = next(
            (a for a in aggregates if a.component == ComponentAggregate.Component.PRACTICAL), None
        )
        self.assertIsNotNone(practical_agg)
        self.assertEqual(practical_agg.mean_score, Decimal("30.00"))

    def test_compute_component_aggregates_with_even_count(self):
        """Test median calculation with even number of results."""
        student2 = Student.objects.create(
            year_class=self.year_class, roll_number="002", official_email="student2@example.com"
        )
        Result.objects.create(
            student=self.student,
            exam=self.exam,
            import_batch=self.import_batch,
            roll_number="001",
            name="Student 1",
            block="A",
            year=2024,
            subject="Math",
            theory=Decimal("70.00"),
            practical=Decimal("30.00"),
            total=Decimal("100.00"),
            grade="A",
            exam_date="2024-01-15",
            status=Result.ResultStatus.PUBLISHED,
        )
        Result.objects.create(
            student=student2,
            exam=self.exam,
            import_batch=self.import_batch,
            roll_number="002",
            name="Student 2",
            block="A",
            year=2024,
            subject="Math",
            theory=Decimal("80.00"),
            practical=Decimal("40.00"),
            total=Decimal("120.00"),
            grade="A",
            exam_date="2024-01-15",
            status=Result.ResultStatus.PUBLISHED,
        )

        aggregates = compute_component_aggregates(self.exam)

        theory_agg = next(
            (a for a in aggregates if a.component == ComponentAggregate.Component.THEORY), None
        )
        self.assertEqual(theory_agg.median_score, Decimal("75.00"))  # (70 + 80) / 2

        practical_agg = next(
            (a for a in aggregates if a.component == ComponentAggregate.Component.PRACTICAL), None
        )
        self.assertEqual(practical_agg.median_score, Decimal("35.00"))  # (30 + 40) / 2

        total_agg = next(
            (a for a in aggregates if a.component == ComponentAggregate.Component.TOTAL), None
        )
        self.assertEqual(total_agg.median_score, Decimal("110.00"))  # (100 + 120) / 2

    def test_compute_component_aggregates_with_no_results(self):
        """Test component aggregate computation with no published results."""
        aggregates = compute_component_aggregates(self.exam)
        self.assertEqual(len(aggregates), 0)


class AnomalyDetectionTests(TestCase):
    """Tests for anomaly detection."""

    def setUp(self):
        """Set up test data."""
        self.year_class = YearClass.objects.create(label="Year 1", order=1)
        self.exam = Exam.objects.create(
            year_class=self.year_class, code="TEST-001", title="Test Exam", exam_date="2024-01-15"
        )

    def test_detect_low_pass_rate_anomaly(self):
        """Test detection of low pass rate."""
        ExamAggregate.objects.create(exam=self.exam, total_students=100, pass_rate=Decimal("30.00"))

        flags = detect_anomalies(self.exam)

        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].flag_type, "LOW_PASS_RATE")
        self.assertEqual(flags[0].severity, AnomalyFlag.Severity.WARNING)

    def test_detect_low_participation_anomaly(self):
        """Test detection of low participation."""
        ExamAggregate.objects.create(exam=self.exam, total_students=5, pass_rate=Decimal("80.00"))

        flags = detect_anomalies(self.exam)

        self.assertTrue(any(f.flag_type == "LOW_PARTICIPATION" for f in flags))

    def test_detect_high_variance_anomaly(self):
        """Test detection of high variance."""
        ExamAggregate.objects.create(
            exam=self.exam,
            total_students=100,
            mean_score=Decimal("50.00"),
            std_dev=Decimal("30.00"),  # 60% of mean
            pass_rate=Decimal("80.00"),
        )

        flags = detect_anomalies(self.exam)

        self.assertTrue(any(f.flag_type == "HIGH_VARIANCE" for f in flags))

    def test_no_anomalies_detected(self):
        """Test when no anomalies exist."""
        ExamAggregate.objects.create(
            exam=self.exam,
            total_students=100,
            mean_score=Decimal("75.00"),
            std_dev=Decimal("10.00"),
            pass_rate=Decimal("85.00"),
        )

        flags = detect_anomalies(self.exam)

        self.assertEqual(len(flags), 0)

    def test_detect_anomalies_without_aggregate(self):
        """Test anomaly detection when no aggregate exists."""
        flags = detect_anomalies(self.exam)
        self.assertEqual(len(flags), 0)


class ComputeAllAnalyticsTests(TestCase):
    """Tests for complete analytics computation."""

    def setUp(self):
        """Set up test data."""
        self.year_class = YearClass.objects.create(label="Year 1", order=1)
        self.exam = Exam.objects.create(
            year_class=self.year_class, code="TEST-001", title="Test Exam", exam_date="2024-01-15"
        )
        self.import_batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.RESULTS, exam=self.exam
        )
        self.student = Student.objects.create(
            year_class=self.year_class, roll_number="001", official_email="student@example.com"
        )

    def test_compute_all_analytics(self):
        """Test complete analytics computation."""
        Result.objects.create(
            student=self.student,
            exam=self.exam,
            import_batch=self.import_batch,
            roll_number="001",
            name="Student",
            block="A",
            year=2024,
            subject="Math",
            theory=Decimal("70.00"),
            practical=Decimal("30.00"),
            total=Decimal("100.00"),
            grade="A",
            exam_date="2024-01-15",
            status=Result.ResultStatus.PUBLISHED,
        )

        result = compute_all_analytics(self.exam)

        self.assertIn("exam_aggregate", result)
        self.assertIn("component_aggregates", result)
        self.assertIn("anomaly_flags", result)

        self.assertIsInstance(result["exam_aggregate"], ExamAggregate)
        self.assertTrue(len(result["component_aggregates"]) > 0)

    def test_compute_all_analytics_clears_old_flags(self):
        """Test that old anomaly flags are cleared."""
        # Create an old flag
        AnomalyFlag.objects.create(
            exam=self.exam, severity=AnomalyFlag.Severity.INFO, flag_type="TEST", message="Old flag"
        )

        self.assertEqual(AnomalyFlag.objects.filter(exam=self.exam).count(), 1)

        compute_all_analytics(self.exam)

        # Old flag should be deleted, and new flags computed (if any)
        flags = AnomalyFlag.objects.filter(exam=self.exam)
        self.assertFalse(any(f.flag_type == "TEST" for f in flags))


class AnalyticsViewTests(TestCase):
    """Tests for analytics views."""

    def setUp(self):
        """Set up test data."""
        self.staff_user = User.objects.create_user(
            username="staff", email="staff@example.com", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", email="regular@example.com"
        )
        self.year_class = YearClass.objects.create(label="Year 1", order=1)
        self.exam = Exam.objects.create(
            year_class=self.year_class, code="TEST-001", title="Test Exam", exam_date="2024-01-15"
        )

    def test_analytics_dashboard_requires_staff(self):
        """Test that dashboard requires staff access."""
        url = reverse("analytics:dashboard")

        # Not logged in - should redirect
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Regular user - should redirect
        self.client.force_login(self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Staff user - should access
        self.client.force_login(self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_analytics_dashboard_displays_data(self):
        """Test dashboard displays analytics data."""
        ExamAggregate.objects.create(
            exam=self.exam,
            total_students=50,
            mean_score=Decimal("75.00"),
            pass_rate=Decimal("80.00"),
        )

        self.client.force_login(self.staff_user)
        url = reverse("analytics:dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TEST-001")
        self.assertContains(response, "50")  # total students

    def test_exam_analytics_detail_requires_staff(self):
        """Test that exam detail requires staff access."""
        url = reverse("analytics:exam_detail", kwargs={"exam_id": self.exam.id})

        # Not logged in - should redirect
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Staff user - should access
        self.client.force_login(self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_exam_analytics_detail_displays_aggregate(self):
        """Test exam detail displays aggregate data."""
        ExamAggregate.objects.create(
            exam=self.exam,
            total_students=50,
            mean_score=Decimal("75.00"),
            median_score=Decimal("74.00"),
            pass_rate=Decimal("80.00"),
            grade_a_count=10,
        )

        self.client.force_login(self.staff_user)
        url = reverse("analytics:exam_detail", kwargs={"exam_id": self.exam.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TEST-001")
        self.assertContains(response, "75.00")  # mean score
        self.assertContains(response, "80.0%")  # pass rate

    def test_exam_analytics_detail_shows_no_data_message(self):
        """Test exam detail shows message when no data available."""
        self.client.force_login(self.staff_user)
        url = reverse("analytics:exam_detail", kwargs={"exam_id": self.exam.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No analytics data available")
