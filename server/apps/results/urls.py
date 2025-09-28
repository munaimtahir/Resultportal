"""URL configuration for results app."""

from django.urls import path
from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("me/", views.StudentProfileView.as_view(), name="student_profile"),
    path("me/results/", views.StudentResultsView.as_view(), name="student_results"),
]