"""Reusable view mixins for account-bound access control."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy

from .models import Student


class StudentAccessRequiredMixin(LoginRequiredMixin):
    """Restrict a view to authenticated users that have an active student profile."""

    login_url = reverse_lazy("accounts:login")
    student: Student | None = None

    def dispatch(self, request, *args, **kwargs):  # type: ignore[override]
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        self.student = self.get_student(request)
        request.student = self.student  # type: ignore[attr-defined]
        return super().dispatch(request, *args, **kwargs)

    def get_student(self, request) -> Student:
        try:
            student = request.user.student_profile  # type: ignore[attr-defined]
        except Student.DoesNotExist as exc:
            raise PermissionDenied("Your account is not linked to a student profile.") from exc

        if not student.is_active:
            raise PermissionDenied("Your student account is inactive.")

        return student

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("student", self.student)
        return context

