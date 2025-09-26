"""Admin configuration for the accounts app."""

from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("roll_number", "display_name", "official_email", "status", "batch_code")
    list_filter = ("status", "batch_code")
    search_fields = ("roll_number", "display_name", "official_email")
    readonly_fields = ("created_at", "updated_at")
