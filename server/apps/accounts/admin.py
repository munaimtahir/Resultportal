"""Admin configuration for the accounts app."""

from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Configuration for managing students in the Django admin."""

    list_display = (
        "official_email",
        "roll_number",
        "display_name",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "official_email",
        "roll_number",
        "display_name",
        "first_name",
        "last_name",
    )
    ordering = ("official_email",)
    readonly_fields = ("created_at", "updated_at")
