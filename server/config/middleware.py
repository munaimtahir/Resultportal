"""Middleware for feature flags and access control."""

from django.conf import settings
from django.http import HttpResponseForbidden
from django.urls import resolve


class ResultsOnlyMiddleware:
    """
    Restrict access to only results-related routes when FEATURE_RESULTS_ONLY is enabled.

    This middleware is useful for production environments where only the results
    portal should be accessible, hiding other features.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Paths that are always allowed
        self.allowed_paths = [
            "/accounts/",
            "/me/",
            "/admin/",
            "/static/",
            "/healthz",
            "/import/",
        ]

    def __call__(self, request):
        if getattr(settings, "FEATURE_RESULTS_ONLY", False):
            path = request.path
            # Check if path starts with any allowed path
            if not any(path.startswith(allowed) for allowed in self.allowed_paths):
                return HttpResponseForbidden(
                    "This feature is currently disabled. "
                    "Only results portal features are available."
                )

        return self.get_response(request)
