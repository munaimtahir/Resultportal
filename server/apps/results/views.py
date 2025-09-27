"""Views for the results app."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView, ListView
from django.contrib import messages
from django.urls import reverse

from apps.accounts.models import Student
from .models import Result


class HomeView(TemplateView):
    """Home page view."""
    template_name = "results/home.html"

    def get(self, request, *args, **kwargs):
        # If user is authenticated and has a student profile, redirect to their profile
        if request.user.is_authenticated and hasattr(request.user, 'student_profile'):
            return redirect('results:student_profile')
        return super().get(request, *args, **kwargs)


class StudentProfileView(LoginRequiredMixin, TemplateView):
    """Student profile page showing basic information."""
    template_name = "results/student_profile.html"
    login_url = "accounts:login"

    def get(self, request, *args, **kwargs):
        # Ensure user has a student profile
        if not hasattr(request.user, 'student_profile') or not request.user.student_profile:
            messages.error(request, "Student profile not found. Please contact the administrator.")
            return redirect('results:home')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student_profile
        context['student'] = student
        context['published_results_count'] = Result.objects.published().filter(student=student).count()
        return context


class StudentResultsView(LoginRequiredMixin, ListView):
    """Student results page showing only their own results."""
    template_name = "results/student_results.html" 
    context_object_name = "results"
    login_url = "accounts:login"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        # Ensure user has a student profile
        if not hasattr(request.user, 'student_profile') or not request.user.student_profile:
            messages.error(request, "Student profile not found. Please contact the administrator.")
            return redirect('results:home')
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        """Return only published results for the authenticated student."""
        student = self.request.user.student_profile
        return Result.objects.published().filter(student=student).order_by('-exam_date', 'subject')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['student'] = self.request.user.student_profile
        return context
