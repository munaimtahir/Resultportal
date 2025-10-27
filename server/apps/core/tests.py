"""Tests for core application functionality."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.core.importers import flatten_validation_errors


class FlattenValidationErrorsTests(TestCase):
    """Tests for the flatten_validation_errors utility function."""

    def test_flatten_dict_errors(self):
        """Test flattening validation errors with message_dict."""
        error = ValidationError({"field1": ["Error 1", "Error 2"], "field2": ["Error 3"]})
        result = flatten_validation_errors(error)
        self.assertIn("field1: Error 1", result)
        self.assertIn("field1: Error 2", result)
        self.assertIn("field2: Error 3", result)

    def test_flatten_list_errors(self):
        """Test flattening validation errors with messages list."""
        error = ValidationError(["Error 1", "Error 2"])
        result = flatten_validation_errors(error)
        self.assertIn("Error 1", result)
        self.assertIn("Error 2", result)

    def test_flatten_string_error(self):
        """Test flattening a single string validation error."""
        error = ValidationError("Single error message")
        result = flatten_validation_errors(error)
        self.assertIn("Single error message", result)


class ImportSummaryTests(TestCase):
    """Tests for the ImportSummary class."""

    def test_has_errors_property(self):
        """Test that has_errors returns True when errors exist."""
        from apps.core.importers import ImportSummary, RowResult
        from apps.results.models import ImportBatch

        batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.STUDENTS,
            is_dry_run=True,
        )

        row_with_error = RowResult(row_number=1, action="skipped", data={})
        row_with_error.errors.append("Test error")

        row_without_error = RowResult(row_number=2, action="created", data={})

        summary = ImportSummary(
            batch=batch,
            created=1,
            updated=0,
            skipped=1,
            row_results=[row_with_error, row_without_error],
        )

        self.assertTrue(summary.has_errors)

    def test_has_errors_false_when_no_errors(self):
        """Test that has_errors returns False when no errors exist."""
        from apps.core.importers import ImportSummary, RowResult
        from apps.results.models import ImportBatch

        batch = ImportBatch.objects.create(
            import_type=ImportBatch.ImportType.STUDENTS,
            is_dry_run=True,
        )

        row_without_error = RowResult(row_number=1, action="created", data={})

        summary = ImportSummary(
            batch=batch,
            created=1,
            updated=0,
            skipped=0,
            row_results=[row_without_error],
        )

        self.assertFalse(summary.has_errors)


class FeatureResultsOnlyMiddlewareTests(TestCase):
    """Tests for FeatureResultsOnlyMiddleware."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            email="test@pmc.edu.pk",
            is_staff=True,
        )

    @override_settings(
        FEATURE_RESULTS_ONLY=True,
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "apps.core.middleware.FeatureResultsOnlyMiddleware",
        ],
    )
    def test_feature_results_only_allows_whitelisted_paths(self):
        """Test that FEATURE_RESULTS_ONLY allows whitelisted paths."""
        self.client.force_login(self.user)

        # These should be allowed (will return 404 or redirect, but not 403)
        allowed_paths = [
            "/admin/",
            "/accounts/login/",
            "/me/",
            "/healthz",
            "/import/students/upload/",
        ]

        for path in allowed_paths:
            response = self.client.get(path)
            # These will return 404, 302, or 200, but not 403
            self.assertNotEqual(
                response.status_code,
                403,
                f"Path {path} should be allowed but got 403",
            )

    @override_settings(
        FEATURE_RESULTS_ONLY=True,
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "apps.core.middleware.FeatureResultsOnlyMiddleware",
        ],
    )
    def test_feature_results_only_blocks_other_paths(self):
        """Test that FEATURE_RESULTS_ONLY blocks non-whitelisted paths."""
        # This should be blocked
        response = self.client.get("/some/other/path/")
        self.assertEqual(response.status_code, 403)

    @override_settings(FEATURE_RESULTS_ONLY=False)
    def test_feature_disabled_allows_all_paths(self):
        """Test that when FEATURE_RESULTS_ONLY is disabled, all paths are allowed."""
        # Should return 404 (not found) not 403 (forbidden)
        response = self.client.get("/some/other/path/")
        self.assertEqual(response.status_code, 404)
