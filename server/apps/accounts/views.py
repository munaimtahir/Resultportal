"""Presentation layer for authentication workflows."""

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView


class GoogleLoginView(TemplateView):
    """Render a simple Google Workspace sign-in page."""

    template_name = "accounts/login.html"

    def dispatch(self, request, *args, **kwargs):  # pragma: no cover - simple guard
        if request.user.is_authenticated:
            messages.info(request, "You are already signed in.")
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "google_login_url": reverse("social:begin", args=["google-oauth2"]),
                "workspace_domain": settings.GOOGLE_WORKSPACE_DOMAIN,
            }
        )
        return context
