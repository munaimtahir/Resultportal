"""URL definitions for the accounts application."""

from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import GoogleLoginView

app_name = "accounts"

urlpatterns = [
    path("login/", GoogleLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
