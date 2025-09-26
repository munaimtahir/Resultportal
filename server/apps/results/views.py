"""Student-facing result views."""

from __future__ import annotations

from django.utils import timezone
from django.views.generic import ListView, TemplateView

from apps.accounts.mixins import StudentAccessRequiredMixin

from .models import Result


class StudentDashboardView(StudentAccessRequiredMixin, TemplateView):
    """Overview page summarising a student's published results."""

    template_name = "results/me_overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        results_qs = (
            Result.objects.published()
            .filter(student=self.student, published_at__lte=timezone.now())
            .order_by("-exam_date", "-updated_at", "subject")
        )

        context.update(
            {
                "published_count": results_qs.count(),
                "recent_results": list(results_qs[:5]),
            }
        )
        context["has_results"] = context["published_count"] > 0

        return context


class StudentResultListView(StudentAccessRequiredMixin, ListView):
    """Detailed list of all published results for the logged-in student."""

    template_name = "results/me_results.html"
    context_object_name = "results"

    def get_queryset(self):
        return (
            Result.objects.published()
            .filter(student=self.student, published_at__lte=timezone.now())
            .order_by("-exam_date", "subject")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        object_list = context.get(self.context_object_name)
        if object_list is not None:
            count = object_list.count() if hasattr(object_list, "count") else len(object_list)
            context["results_count"] = count
            context["has_results"] = count > 0
        else:  # pragma: no cover - defensive
            context["results_count"] = 0
            context["has_results"] = False
        return context

