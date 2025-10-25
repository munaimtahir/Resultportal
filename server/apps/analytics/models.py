"""Analytics domain models for cohort statistics and dashboards."""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.results.models import Exam
from apps.accounts.models import YearClass


class ExamAggregate(models.Model):
    """Statistical aggregates for an exam."""
    
    exam = models.OneToOneField(
        Exam,
        on_delete=models.CASCADE,
        related_name="aggregate",
        help_text="Exam these aggregates are for"
    )
    
    # Basic statistics
    total_students = models.PositiveIntegerField(default=0)
    mean_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    median_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    std_dev = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    min_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Pass/Fail metrics
    pass_count = models.PositiveIntegerField(default=0)
    fail_count = models.PositiveIntegerField(default=0)
    pass_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Grade distribution (A, B, C, D, F counts)
    grade_a_count = models.PositiveIntegerField(default=0)
    grade_b_count = models.PositiveIntegerField(default=0)
    grade_c_count = models.PositiveIntegerField(default=0)
    grade_d_count = models.PositiveIntegerField(default=0)
    grade_f_count = models.PositiveIntegerField(default=0)
    
    computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ("-computed_at",)
    
    def __str__(self) -> str:
        return f"Aggregates for {self.exam.code}"


class ComponentAggregate(models.Model):
    """Component-wise statistics (Theory, Practical, etc.)."""
    
    class Component(models.TextChoices):
        THEORY = "THEORY", "Theory/Written"
        PRACTICAL = "PRACTICAL", "Practical/Viva"
        TOTAL = "TOTAL", "Total"
    
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="component_aggregates",
    )
    component = models.CharField(max_length=20, choices=Component.choices)
    
    mean_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    median_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    std_dev = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ("-computed_at", "component")
        unique_together = [["exam", "component"]]
    
    def __str__(self) -> str:
        return f"{self.exam.code} - {self.get_component_display()}"


# Placeholder models for future implementation
class ComparisonAggregate(models.Model):
    """Year-over-year comparison metrics."""
    
    current_exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="comparison_as_current")
    previous_exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="comparison_as_previous", null=True, blank=True)
    
    mean_delta = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    pass_rate_delta = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cohens_d = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    
    computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TrendAggregate(models.Model):
    """Multi-session trend analysis."""
    
    year_class = models.ForeignKey(YearClass, on_delete=models.CASCADE, related_name="trends")
    period_label = models.CharField(max_length=100)
    
    trend_data = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AnomalyFlag(models.Model):
    """Detected anomalies and alerts."""
    
    class Severity(models.TextChoices):
        INFO = "INFO", "Information"
        WARNING = "WARNING", "Warning"
        CRITICAL = "CRITICAL", "Critical"
    
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="anomalies")
    severity = models.CharField(max_length=20, choices=Severity.choices)
    flag_type = models.CharField(max_length=100)
    message = models.TextField()
    
    detected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ("-detected_at",)

