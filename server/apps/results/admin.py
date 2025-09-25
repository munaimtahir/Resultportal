from django.contrib import admin

from .models import ImportBatch, Result


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        "import_type",
        "is_dry_run",
        "row_count",
        "created_rows",
        "updated_rows",
        "skipped_rows",
        "started_by",
        "created_at",
    )
    list_filter = ("import_type", "is_dry_run", "created_at")
    search_fields = ("source_filename", "notes", "started_by__email")


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "subject",
        "year",
        "grade",
        "total_marks",
        "exam_date",
        "is_published",
    )
    list_filter = ("subject", "year", "grade", "published_at")
    search_fields = (
        "student__official_email",
        "student__roll_number",
        "subject",
        "grade",
    )
