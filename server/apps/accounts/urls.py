"""URL definitions for the accounts application."""

from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    GoogleLoginView,
    TokenAuthenticateView,
    TokenRequestView,
    TokenSuccessView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", GoogleLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/request/", TokenRequestView.as_view(), name="token_request"),
    path("token/success/", TokenSuccessView.as_view(), name="token_success"),
    path("token/authenticate/", TokenAuthenticateView.as_view(), name="token_authenticate"),
]
