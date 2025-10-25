"""Tests for core application functionality."""

from django.core.exceptions import ValidationError
from django.test import TestCase

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
