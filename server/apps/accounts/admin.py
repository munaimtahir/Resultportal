"""Admin configuration for the accounts app."""

from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "official_email",
        "roll_number",
        "display_name",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("official_email", "roll_number", "display_name")
    ordering = ("official_email",)
    autocomplete_fields = ("user",)
