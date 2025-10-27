"""URL configuration for results app."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("me/", views.StudentProfileView.as_view(), name="student_profile"),
    path("me/results/", views.StudentResultsView.as_view(), name="student_results"),
    # CSV Import URLs
    path("import/students/upload/", views.StudentCSVUploadView.as_view(), name="upload_students"),
    path(
        "import/students/preview/",
        views.StudentCSVPreviewView.as_view(),
        name="import_preview_students",
    ),
    path("import/results/upload/", views.ResultCSVUploadView.as_view(), name="upload_results"),
    path(
        "import/results/preview/",
        views.ResultCSVPreviewView.as_view(),
        name="import_preview_results",
    ),
]
