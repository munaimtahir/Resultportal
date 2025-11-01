"""Views for analytics functionality."""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

from apps.results.models import Exam

from .models import AnomalyFlag, ComponentAggregate, ExamAggregate


@staff_member_required
def analytics_dashboard(request):
    """Display analytics dashboard for staff members."""
    # Get recent exam aggregates
    recent_aggregates = ExamAggregate.objects.select_related('exam').all()[:20]
    
    # Get recent anomaly flags
    recent_anomalies = AnomalyFlag.objects.select_related('exam').filter(
        severity__in=[AnomalyFlag.Severity.WARNING, AnomalyFlag.Severity.CRITICAL]
    )[:10]
    
    context = {
        'recent_aggregates': recent_aggregates,
        'recent_anomalies': recent_anomalies,
        'total_exams_analyzed': ExamAggregate.objects.count(),
        'total_anomalies': AnomalyFlag.objects.count(),
    }
    
    return render(request, 'analytics/dashboard.html', context)


@staff_member_required
def exam_analytics_detail(request, exam_id):
    """Display detailed analytics for a specific exam."""
    exam = get_object_or_404(Exam, pk=exam_id)
    
    try:
        exam_aggregate = ExamAggregate.objects.get(exam=exam)
    except ExamAggregate.DoesNotExist:
        exam_aggregate = None
    
    component_aggregates = ComponentAggregate.objects.filter(exam=exam).order_by('component')
    anomaly_flags = AnomalyFlag.objects.filter(exam=exam).order_by('-detected_at')
    
    context = {
        'exam': exam,
        'exam_aggregate': exam_aggregate,
        'component_aggregates': component_aggregates,
        'anomaly_flags': anomaly_flags,
    }
    
    return render(request, 'analytics/exam_detail.html', context)

