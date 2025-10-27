"""Admin configuration for the accounts app."""

from django.contrib import admin

from .models import Student, StudentAccessToken, YearClass


@admin.register(YearClass)
class YearClassAdmin(admin.ModelAdmin):
    """Configuration for managing year/classes in the Django admin."""

    list_display = ("label", "order", "created_at")
    ordering = ("order",)
    search_fields = ("label",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Configuration for managing students in the Django admin."""

    list_display = (
        "official_email",
        "roll_number",
        "display_name",
        "year_class",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "year_class", "created_at")
    search_fields = (
        "official_email",
        "roll_number",
        "display_name",
        "first_name",
        "last_name",
        "phone",
    )
    ordering = ("official_email",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(StudentAccessToken)
class StudentAccessTokenAdmin(admin.ModelAdmin):
    """Configuration for managing student access tokens in the Django admin."""

    list_display = ("student", "code", "expires_at", "used_at", "created_at")
    list_filter = ("expires_at", "used_at", "created_at")
    search_fields = ("student__roll_number", "student__official_email", "code")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "used_at")

    def get_readonly_fields(self, request, obj=None):  # pragma: no cover
        """Make code readonly after creation."""
        if obj:  # Editing an existing object
            return self.readonly_fields + ("code", "student", "expires_at")
        return self.readonly_fields
