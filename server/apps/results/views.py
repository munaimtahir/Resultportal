"""Views for the results app."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import ListView, TemplateView

from apps.accounts.models import Student

from .models import Result


class TokenOrLoginRequiredMixin:
    """Mixin to require either token-based or standard authentication."""

    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated via standard login
        if request.user.is_authenticated and hasattr(request.user, "student_profile"):
            return super().dispatch(request, *args, **kwargs)
        
        # Check if user is authenticated via token
        if request.session.get("token_authenticated") and request.session.get("token_student_id"):
            return super().dispatch(request, *args, **kwargs)
        
        # Not authenticated either way - redirect to token login
        messages.error(request, "Please log in to access your results.")
        return redirect("accounts:token_authenticate")

    def get_student(self):
        """Get the student for the current request (from user or token)."""
        # Standard authentication
        if self.request.user.is_authenticated and hasattr(self.request.user, "student_profile"):
            return self.request.user.student_profile
        
        # Token authentication
        student_id = self.request.session.get("token_student_id")
        if student_id:
            try:
                return Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                pass
        
        return None


class HomeView(TemplateView):
    """Home page view."""

    template_name = "results/home.html"

    def get(self, request, *args, **kwargs):
        # If user is authenticated and has a student profile, redirect to their profile
        if request.user.is_authenticated and hasattr(request.user, "student_profile"):
            return redirect("results:student_profile")
        # Check token-based authentication
        if request.session.get("token_authenticated") and request.session.get("token_student_id"):
            return redirect("results:student_profile")
        return super().get(request, *args, **kwargs)


class StudentProfileView(TokenOrLoginRequiredMixin, TemplateView):
    """Student profile page showing basic information."""

    template_name = "results/student_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_student()
        if not student:
            return context
        
        context["student"] = student
        context["published_results_count"] = (
            Result.objects.published().filter(student=student).count()
        )
        # Include exam information with recheck availability
        from apps.results.models import Exam
        from django.utils import timezone
        
        exams_with_results = []
        for result in Result.objects.published().filter(student=student).select_related('exam'):
            if result.exam and result.exam not in [e['exam'] for e in exams_with_results]:
                exams_with_results.append({
                    'exam': result.exam,
                    'recheck_open': result.exam.is_recheck_open() if result.exam else False,
                })
        context["exams_with_results"] = exams_with_results
        
        return context


class StudentResultsView(TokenOrLoginRequiredMixin, ListView):
    """Student results page showing only their own results."""

    template_name = "results/student_results.html"
    context_object_name = "results"
    paginate_by = 20

    def get_queryset(self):
        """Return only published results for the authenticated student."""
        student = self.get_student()
        if not student:
            return Result.objects.none()
        return Result.objects.published().filter(student=student).order_by("-exam_date", "subject")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_student()
        context["student"] = student
        return context

