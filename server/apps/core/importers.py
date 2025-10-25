"""Shared import utilities for CSV workflows."""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from collections.abc import Iterable
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import IO, TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import transaction

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

    batch: ImportBatch
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


class BaseCSVImporter(ABC):
    """Base class for CSV importers with shared functionality."""

    def __init__(
        self,
        stream: IO[str],
        *,
        started_by=None,
        filename: str | None = None,
        notes: str | None = None,
    ) -> None:
        self.stream = stream
        self.started_by = started_by
        self.filename = filename or ""
        self.notes = notes or ""

    def preview(self) -> ImportSummary:
        """Run a dry-run import producing per-row validation feedback."""
        return self._process(dry_run=True)

    def commit(self) -> ImportSummary:
        """Persist changes after successful validation."""
        return self._process(dry_run=False)

    def _rewind_stream(self) -> None:
        """Rewind the stream to the beginning for re-reading."""
        try:
            self.stream.seek(0)
        except (AttributeError, OSError):  # pragma: no cover - defensive
            pass

    @abstractmethod
    def _get_import_type(self) -> ImportBatch.ImportType:
        """Return the import type for batch creation."""
        pass

    @abstractmethod
    def _validate_headers(self, headers: Iterable[str] | None) -> None:
        """Validate the CSV headers."""
        pass

    @abstractmethod
    def _process_row(
        self, row_number: int, normalised: dict[str, str], dry_run: bool, batch: ImportBatch
    ) -> tuple[str, int, int, int, RowResult]:
        """
        Process a single row and return action and counters.

        Args:
            row_number: Current row number being processed
            normalised: Dict of normalised row data
            dry_run: Whether this is a dry run
            batch: The ImportBatch instance for this import

        Returns:
            tuple: (action, created_delta, updated_delta, skipped_delta, row_result)
        """
        pass

    def _process(self, *, dry_run: bool) -> ImportSummary:
        """Core processing logic shared by both importers."""
        from apps.results.models import ImportBatch  # Avoid circular import

        self._rewind_stream()
        reader = csv.DictReader(self.stream)
        self._validate_headers(reader.fieldnames)

        batch = ImportBatch.objects.create(
            import_type=self._get_import_type(),
            started_by=self.started_by,
            source_filename=self.filename,
            notes=self.notes,
            is_dry_run=dry_run,
        )

        row_results: list[RowResult] = []
        created = updated = skipped = 0

        context = transaction.atomic() if not dry_run else nullcontext()
        with context:
            for row_number, raw_row in enumerate(reader, start=2):
                normalised = {key: (value or "").strip() for key, value in raw_row.items()}

                action, created_delta, updated_delta, skipped_delta, row_result = self._process_row(
                    row_number, normalised, dry_run, batch
                )

                created += created_delta
                updated += updated_delta
                skipped += skipped_delta
                row_results.append(row_result)

            batch.row_count = len(row_results)
            batch.created_rows = created
            batch.updated_rows = updated
            batch.skipped_rows = skipped
            batch.save(
                update_fields=[
                    "row_count",
                    "created_rows",
                    "updated_rows",
                    "skipped_rows",
                ]
            )

            if not dry_run:
                batch.mark_completed()

        return ImportSummary(
            batch=batch,
            created=created,
            updated=updated,
            skipped=skipped,
            row_results=row_results,
        )


def flatten_validation_errors(error: ValidationError) -> list[str]:
    """Extract validation error messages into a flat list."""
    messages: list[str] = []
    try:
        # Try to access message_dict for field-specific errors
        message_dict = error.message_dict
        if isinstance(message_dict, dict):
            for field, field_errors in message_dict.items():
                for field_error in field_errors:
                    messages.append(f"{field}: {field_error}")
        else:  # pragma: no cover - unreachable in Django's ValidationError
            messages.extend(error.messages)
    except AttributeError:
        # Fall back to general error messages when message_dict is not available
        messages.extend(error.messages)
    return messages
