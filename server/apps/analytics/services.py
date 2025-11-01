"""Analytics computation services for exam aggregates and statistics."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q, StdDev

from apps.results.models import Exam, Result

from .models import AnomalyFlag, ComponentAggregate, ExamAggregate


def compute_exam_aggregates(exam: Exam) -> ExamAggregate:
    """
    Compute and persist statistical aggregates for an exam.
    
    Args:
        exam: The exam to compute aggregates for
        
    Returns:
        The created or updated ExamAggregate instance
    """
    # Get all published results for this exam
    results = Result.objects.filter(
        exam=exam,
        status=Result.ResultStatus.PUBLISHED,
        total__isnull=False
    )
    
    # Compute basic statistics
    stats = results.aggregate(
        total_students=Count('id'),
        mean_score=Avg('total'),
        min_score=Min('total'),
        max_score=Max('total'),
        std_dev=StdDev('total'),
    )
    
    # Compute median manually
    count = stats['total_students']
    median_score = None
    if count > 0:
        ordered = results.order_by('total').values_list('total', flat=True)
        if count % 2 == 1:
            median_score = ordered[count // 2]
        else:
            median_score = (ordered[count // 2 - 1] + ordered[count // 2]) / 2
    
    # Compute pass/fail metrics (assuming grade 'F' means fail)
    pass_count = results.exclude(grade='F').count()
    fail_count = results.filter(grade='F').count()
    pass_rate = (pass_count / count * 100) if count > 0 else None
    
    # Compute grade distribution
    grade_counts = {
        'A': results.filter(grade='A').count(),
        'B': results.filter(grade='B').count(),
        'C': results.filter(grade='C').count(),
        'D': results.filter(grade='D').count(),
        'F': results.filter(grade='F').count(),
    }
    
    # Create or update the aggregate
    aggregate, created = ExamAggregate.objects.update_or_create(
        exam=exam,
        defaults={
            'total_students': stats['total_students'],
            'mean_score': stats['mean_score'],
            'median_score': median_score,
            'std_dev': stats['std_dev'],
            'min_score': stats['min_score'],
            'max_score': stats['max_score'],
            'pass_count': pass_count,
            'fail_count': fail_count,
            'pass_rate': pass_rate,
            'grade_a_count': grade_counts['A'],
            'grade_b_count': grade_counts['B'],
            'grade_c_count': grade_counts['C'],
            'grade_d_count': grade_counts['D'],
            'grade_f_count': grade_counts['F'],
        }
    )
    
    return aggregate


def compute_component_aggregates(exam: Exam) -> list[ComponentAggregate]:
    """
    Compute and persist component-wise statistics for an exam.
    
    Args:
        exam: The exam to compute component aggregates for
        
    Returns:
        List of created or updated ComponentAggregate instances
    """
    results = Result.objects.filter(
        exam=exam,
        status=Result.ResultStatus.PUBLISHED
    )
    
    aggregates = []
    
    # Theory component
    theory_results = results.filter(theory__isnull=False)
    if theory_results.exists():
        theory_stats = theory_results.aggregate(
            mean=Avg('theory'),
            std_dev=StdDev('theory'),
        )
        theory_count = theory_results.count()
        theory_ordered = theory_results.order_by('theory').values_list('theory', flat=True)
        theory_median = None
        if theory_count > 0:
            if theory_count % 2 == 1:
                theory_median = theory_ordered[theory_count // 2]
            else:
                theory_median = (theory_ordered[theory_count // 2 - 1] + theory_ordered[theory_count // 2]) / 2
        
        agg, _ = ComponentAggregate.objects.update_or_create(
            exam=exam,
            component=ComponentAggregate.Component.THEORY,
            defaults={
                'mean_score': theory_stats['mean'],
                'median_score': theory_median,
                'std_dev': theory_stats['std_dev'],
            }
        )
        aggregates.append(agg)
    
    # Practical component
    practical_results = results.filter(practical__isnull=False)
    if practical_results.exists():
        practical_stats = practical_results.aggregate(
            mean=Avg('practical'),
            std_dev=StdDev('practical'),
        )
        practical_count = practical_results.count()
        practical_ordered = practical_results.order_by('practical').values_list('practical', flat=True)
        practical_median = None
        if practical_count > 0:
            if practical_count % 2 == 1:
                practical_median = practical_ordered[practical_count // 2]
            else:
                practical_median = (practical_ordered[practical_count // 2 - 1] + practical_ordered[practical_count // 2]) / 2
        
        agg, _ = ComponentAggregate.objects.update_or_create(
            exam=exam,
            component=ComponentAggregate.Component.PRACTICAL,
            defaults={
                'mean_score': practical_stats['mean'],
                'median_score': practical_median,
                'std_dev': practical_stats['std_dev'],
            }
        )
        aggregates.append(agg)
    
    # Total component
    total_results = results.filter(total__isnull=False)
    if total_results.exists():
        total_stats = total_results.aggregate(
            mean=Avg('total'),
            std_dev=StdDev('total'),
        )
        total_count = total_results.count()
        total_ordered = total_results.order_by('total').values_list('total', flat=True)
        total_median = None
        if total_count > 0:
            if total_count % 2 == 1:
                total_median = total_ordered[total_count // 2]
            else:
                total_median = (total_ordered[total_count // 2 - 1] + total_ordered[total_count // 2]) / 2
        
        agg, _ = ComponentAggregate.objects.update_or_create(
            exam=exam,
            component=ComponentAggregate.Component.TOTAL,
            defaults={
                'mean_score': total_stats['mean'],
                'median_score': total_median,
                'std_dev': total_stats['std_dev'],
            }
        )
        aggregates.append(agg)
    
    return aggregates


def detect_anomalies(exam: Exam) -> list[AnomalyFlag]:
    """
    Detect anomalies in exam results and create flags.
    
    Args:
        exam: The exam to check for anomalies
        
    Returns:
        List of created AnomalyFlag instances
    """
    flags = []
    
    try:
        aggregate = ExamAggregate.objects.get(exam=exam)
    except ExamAggregate.DoesNotExist:
        return flags
    
    # Check for unusually low pass rate
    if aggregate.pass_rate is not None and aggregate.pass_rate < 50:
        flag = AnomalyFlag.objects.create(
            exam=exam,
            severity=AnomalyFlag.Severity.WARNING,
            flag_type='LOW_PASS_RATE',
            message=f'Pass rate is unusually low: {aggregate.pass_rate:.2f}%'
        )
        flags.append(flag)
    
    # Check for very low participation
    if aggregate.total_students < 10:
        flag = AnomalyFlag.objects.create(
            exam=exam,
            severity=AnomalyFlag.Severity.INFO,
            flag_type='LOW_PARTICIPATION',
            message=f'Only {aggregate.total_students} students participated in this exam'
        )
        flags.append(flag)
    
    # Check for high standard deviation (indicates inconsistent results)
    if aggregate.std_dev is not None and aggregate.mean_score is not None:
        if aggregate.std_dev > aggregate.mean_score * Decimal('0.4'):
            flag = AnomalyFlag.objects.create(
                exam=exam,
                severity=AnomalyFlag.Severity.INFO,
                flag_type='HIGH_VARIANCE',
                message=f'High score variance detected (std dev: {aggregate.std_dev:.2f})'
            )
            flags.append(flag)
    
    return flags


@transaction.atomic
def compute_all_analytics(exam: Exam) -> dict[str, Any]:
    """
    Compute all analytics for an exam in a single transaction.
    
    Args:
        exam: The exam to compute analytics for
        
    Returns:
        Dictionary with computed aggregates and flags
    """
    # Clear existing anomaly flags for this exam
    AnomalyFlag.objects.filter(exam=exam).delete()
    
    exam_aggregate = compute_exam_aggregates(exam)
    component_aggregates = compute_component_aggregates(exam)
    anomaly_flags = detect_anomalies(exam)
    
    return {
        'exam_aggregate': exam_aggregate,
        'component_aggregates': component_aggregates,
        'anomaly_flags': anomaly_flags,
    }
