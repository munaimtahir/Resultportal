"""Middleware for feature flags."""

from django.conf import settings
from django.http import HttpResponseForbidden
from django.urls import resolve


class FeatureResultsOnlyMiddleware:
    """
    Middleware to restrict access to non-results routes when FEATURE_RESULTS_ONLY is enabled.

    When this feature flag is enabled, only the following routes are allowed:
    - /admin/ (for staff)
    - /accounts/ (for authentication)
    - /auth/ (for social auth)
    - /import/ (for CSV imports)
    - /me/ (for student profile and results)
    - /healthz (for health checks)
    """

    ALLOWED_PREFIXES = [
        "/admin/",
        "/accounts/",
        "/auth/",
        "/import/",
        "/me/",
        "/healthz",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if feature flag is enabled
        if getattr(settings, "FEATURE_RESULTS_ONLY", False):
            path = request.path

            # Allow whitelisted paths
            if any(path.startswith(prefix) for prefix in self.ALLOWED_PREFIXES):
                return self.get_response(request)

            # Block all other paths
            return HttpResponseForbidden(
                "Access to this feature is restricted. Only results-related functionality is currently available."
            )

        # Feature flag not enabled, allow all requests
        return self.get_response(request)  # pragma: no cover - default behavior
