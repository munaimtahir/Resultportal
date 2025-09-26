"""URL patterns for student-facing result pages."""

from django.urls import path
from django.views.generic import RedirectView

from .views import StudentDashboardView, StudentResultListView

app_name = "results"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="results:me", permanent=False), name="home"),
    path("me/", StudentDashboardView.as_view(), name="me"),
    path("me/results/", StudentResultListView.as_view(), name="me-results"),
]

