"""Admin configuration for the accounts app."""

from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("official_email", "user", "updated_at")
    search_fields = ("official_email", "user__username", "user__email")
    list_filter = ("updated_at",)
