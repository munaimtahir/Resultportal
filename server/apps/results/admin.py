"""Django admin configuration for results app."""

import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import Exam, ImportBatch, Result


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    """Configuration for managing exams in the Django admin."""

    list_display = (
        "code",
        "title",
        "year_class",
        "kind",
        "exam_date",
        "recheck_deadline",
        "created_at",
    )
    list_filter = ("kind", "year_class", "exam_date", "created_at")
    search_fields = ("code", "title", "block_letter")
    ordering = ("-exam_date", "code")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Information", {"fields": ("year_class", "code", "title", "kind")}),
        ("Exam Details", {"fields": ("block_letter", "exam_date")}),
        (
            "Recheck Information",
            {"fields": ("recheck_form_url", "recheck_deadline"), "classes": ("collapse",)},
        ),
        ("Metadata", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "import_type",
        "exam",
        "is_dry_run",
        "row_count",
        "created_rows",
        "updated_rows",
        "skipped_rows",
        "started_by",
        "created_at",
    )
    list_filter = ("import_type", "is_dry_run", "exam", "created_at")
    search_fields = ("source_filename", "notes", "started_by__email")
    readonly_fields = ("created_at", "completed_at")


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam",
        "subject",
        "year",
        "status",
        "grade",
        "total_marks",
        "exam_date",
        "verified_by",
    )
    list_filter = ("status", "subject", "year", "grade", "exam", "import_batch")
    search_fields = (
        "student__official_email",
        "student__roll_number",
        "subject",
        "grade",
        "exam__code",
    )
    readonly_fields = ("created_at", "updated_at", "verified_at", "published_at")

    fieldsets = (
        ("Student Information", {"fields": ("student", "roll_number", "name")}),
        ("Exam Information", {"fields": ("exam", "subject", "year", "block", "exam_date")}),
        ("Marks", {"fields": (("theory", "practical", "total"), "grade")}),
        (
            "Workflow",
            {
                "fields": ("status", "verified_by", "verified_at", "published_at"),
                "classes": ("collapse",),
            },
        ),
        ("Import Details", {"fields": ("import_batch", "respondent_id"), "classes": ("collapse",)}),
        (
            "Audit Trail",
            {"fields": ("status_log", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    actions = [
        "verify_results",
        "return_results",
        "publish_results",
        "unpublish_results",
        "export_as_csv",
    ]

    def verify_results(self, request, queryset):  # pragma: no cover - admin action
        """Bulk verify selected results (SUBMITTED → VERIFIED)."""
        count = 0
        for result in queryset:
            if result.status == result.ResultStatus.SUBMITTED:
                result.verify(request.user)
                count += 1
        self.message_user(request, f"Verified {count} result(s).")

    verify_results.short_description = "Verify selected results"

    def return_results(self, request, queryset):  # pragma: no cover - admin action
        """Bulk return selected results for correction (SUBMITTED → RETURNED)."""
        count = 0
        for result in queryset:
            if result.status == result.ResultStatus.SUBMITTED:
                result.return_for_correction(request.user)
                count += 1
        self.message_user(request, f"Returned {count} result(s) for correction.")

    return_results.short_description = "Return selected results for correction"

    def publish_results(self, request, queryset):  # pragma: no cover - admin action
        """Bulk publish selected results (VERIFIED → PUBLISHED)."""
        count = 0
        for result in queryset:
            if result.status == result.ResultStatus.VERIFIED:
                result.publish(request.user)
                count += 1
        self.message_user(request, f"Published {count} result(s).")

    publish_results.short_description = "Publish selected results"

    def unpublish_results(self, request, queryset):  # pragma: no cover - admin action
        """Bulk unpublish selected results (PUBLISHED → VERIFIED)."""
        count = 0
        for result in queryset:
            if result.status == result.ResultStatus.PUBLISHED:
                result.unpublish(request.user)
                count += 1
        self.message_user(request, f"Unpublished {count} result(s).")

    unpublish_results.short_description = "Unpublish selected results"

    def export_as_csv(self, request, queryset):  # pragma: no cover - admin action
        """Export selected results as CSV."""
        meta = self.model._meta
        field_names = [
            "roll_number",
            "name",
            "subject",
            "theory",
            "practical",
            "total",
            "grade",
            "exam_date",
            "status",
        ]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=results_export.csv"
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            row = [getattr(obj, field) for field in field_names]
            writer.writerow(row)

        return response

    export_as_csv.short_description = "Export selected results as CSV"
