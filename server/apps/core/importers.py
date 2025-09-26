"""Shared import utilities for CSV workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from apps.results.models import ImportBatch


@dataclass(slots=True)
class RowResult:
    """Represents the outcome of processing a single CSV row."""

    row_number: int
    action: str
    errors: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


@dataclass(slots=True)
class ImportSummary:
    """Summary information returned after running an importer."""

    batch: "ImportBatch"
    created: int
    updated: int
    skipped: int
    row_results: list[RowResult]

    @property
    def row_count(self) -> int:
        return len(self.row_results)

    @property
    def has_errors(self) -> bool:
        return any(row.has_errors for row in self.row_results)


