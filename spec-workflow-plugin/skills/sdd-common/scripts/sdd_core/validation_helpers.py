"""Shared validation helpers for SDD scripts.

Deduplicates the file-exists + JSON-read + early-return pattern
used across check-status, check-re-review, and validate-review-artifact scripts,
plus a small formatter used by review-pipeline validators.

Also hosts the canonical :class:`Severity` enum shared by task prompt
validation (``sdd_core.task_validation``) and skill reference-depth
invariants (``tests/_support/skill_reference``). One enum keeps the
wire-level vocabulary (``"error"`` / ``"warning"``) consistent across
CI reporters, review artifacts, and per-rule tests.
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Any

from . import output

__all__ = ["load_json_file_or_none", "format_error_list", "Severity"]


class Severity(str, Enum):
    """Shared severity vocabulary for validation findings."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


def load_json_file_or_none(path: str, *, default: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Read a JSON file, returning parsed data or ``None`` if missing.

    Callers handle the missing-file case (e.g. emitting output, raising, etc.).
    When the file exists but is empty/unparseable-as-dict, *default* (or ``{}``)
    is returned instead.
    """
    if not os.path.isfile(path):
        return None
    return output.safe_read_json(path, default=default if default is not None else {})


def format_error_list(errors: list[str], *, separator: str = "; ") -> str:
    """Format a list of validation errors into a single string."""
    return separator.join(errors)
