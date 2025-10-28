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
    search_fields = ("source_filename", "csv_filename", "notes", "started_by__email")
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
    list_filter = ("status", "subject", "year", "grade", "exam", "published_at")
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

    def verify_results(self, request, queryset):
        """Bulk verify selected results."""
        count = 0
        for result in queryset:
            if result.status == result.ResultStatus.SUBMITTED:
                result.verify(request.user)
                count += 1
        self.message_user(request, f"Verified {count} result(s).")

    verify_results.short_description = "Verify selected results"

    def return_results(self, request, queryset):
        """Bulk return selected results for correction."""
        count = 0
        for result in queryset:
            if result.status == result.ResultStatus.SUBMITTED:
                result.return_for_correction(user=request.user)
                count += 1
        self.message_user(request, f"Returned {count} result(s) for correction.")

    return_results.short_description = "Return selected results for correction"

    def publish_results(self, request, queryset):
        """Bulk publish selected results."""
        from django.conf import settings

        # Check ALLOW_PUBLISH flag
        if not getattr(settings, "ALLOW_PUBLISH", True):
            self.message_user(
                request,
                "Publishing is currently disabled by system configuration.",
                level="error",
            )
            return

        count = 0
        for result in queryset:
            if result.status in [result.ResultStatus.VERIFIED, result.ResultStatus.DRAFT]:
                result.publish(request.user)
                count += 1
        self.message_user(request, f"Published {count} result(s).")

    publish_results.short_description = "Publish selected results"

    def unpublish_results(self, request, queryset):
        """Bulk unpublish selected results."""
        count = 0
        for result in queryset:
            if result.status == result.ResultStatus.PUBLISHED:
                result.unpublish(request.user)
                count += 1
        self.message_user(request, f"Unpublished {count} result(s).")

    unpublish_results.short_description = "Unpublish selected results"

    def export_as_csv(self, request, queryset):
        """Export selected results as CSV."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="results_export.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Roll Number",
                "Name",
                "Subject",
                "Year",
                "Block",
                "Theory",
                "Practical",
                "Total",
                "Grade",
                "Status",
                "Exam Date",
                "Exam Code",
                "Verified By",
                "Published At",
            ]
        )

        for result in queryset:
            writer.writerow(
                [
                    result.roll_number,
                    result.name,
                    result.subject,
                    result.year,
                    result.block,
                    result.theory,
                    result.practical,
                    result.total,
                    result.grade,
                    result.status,
                    result.exam_date,
                    result.exam.code if result.exam else "",
                    result.verified_by.username if result.verified_by else "",
                    result.published_at,
                ]
            )

        return response

    export_as_csv.short_description = "Export selected results as CSV"
