"""Admin configuration for the analytics app."""

from django.contrib import admin

from .models import (
    AnomalyFlag,
    ComparisonAggregate,
    ComponentAggregate,
    ExamAggregate,
    TrendAggregate,
)


@admin.register(ExamAggregate)
class ExamAggregateAdmin(admin.ModelAdmin):
    """Configuration for managing exam aggregates in the Django admin."""

    list_display = (
        "exam",
        "total_students",
        "mean_score",
        "pass_rate",
        "computed_at",
    )
    list_filter = ("computed_at", "exam__year_class")
    search_fields = ("exam__code", "exam__title")
    readonly_fields = ("computed_at", "created_at")
    ordering = ("-computed_at",)


@admin.register(ComponentAggregate)
class ComponentAggregateAdmin(admin.ModelAdmin):
    """Configuration for managing component aggregates in the Django admin."""

    list_display = (
        "exam",
        "component",
        "mean_score",
        "median_score",
        "std_dev",
        "computed_at",
    )
    list_filter = ("component", "computed_at", "exam__year_class")
    search_fields = ("exam__code", "exam__title")
    readonly_fields = ("computed_at", "created_at")
    ordering = ("-computed_at", "component")


@admin.register(ComparisonAggregate)
class ComparisonAggregateAdmin(admin.ModelAdmin):
    """Configuration for managing comparison aggregates in the Django admin."""

    list_display = (
        "current_exam",
        "previous_exam",
        "mean_delta",
        "pass_rate_delta",
        "cohens_d",
        "computed_at",
    )
    list_filter = ("computed_at",)
    search_fields = ("current_exam__code", "previous_exam__code")
    readonly_fields = ("computed_at", "created_at")
    ordering = ("-computed_at",)


@admin.register(TrendAggregate)
class TrendAggregateAdmin(admin.ModelAdmin):
    """Configuration for managing trend aggregates in the Django admin."""

    list_display = ("year_class", "period_label", "computed_at")
    list_filter = ("year_class", "computed_at")
    search_fields = ("period_label",)
    readonly_fields = ("computed_at", "created_at")
    ordering = ("-computed_at",)


@admin.register(AnomalyFlag)
class AnomalyFlagAdmin(admin.ModelAdmin):
    """Configuration for managing anomaly flags in the Django admin."""

    list_display = (
        "exam",
        "severity",
        "flag_type",
        "message",
        "detected_at",
    )
    list_filter = ("severity", "flag_type", "detected_at", "exam__year_class")
    search_fields = ("exam__code", "flag_type", "message")
    readonly_fields = ("detected_at",)
    ordering = ("-detected_at",)

    def has_add_permission(self, request):  # pragma: no cover - admin override
        """Anomalies are auto-generated, not manually created."""
        return False
