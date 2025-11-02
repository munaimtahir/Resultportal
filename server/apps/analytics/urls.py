"""URL configuration for analytics app."""

from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("dashboard/", views.analytics_dashboard, name="dashboard"),
    path("exam/<int:exam_id>/", views.exam_analytics_detail, name="exam_detail"),
]
