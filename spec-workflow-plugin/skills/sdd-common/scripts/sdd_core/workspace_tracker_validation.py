"""Schema validation and constraint checks for workspace tracker data."""
from __future__ import annotations

import warnings as _warnings
from typing import TYPE_CHECKING

from . import output
from .specs import DOC_NAMES

__all__ = [
    "TRACKER_SCHEMA_VERSION",
    "VALID_APPROVAL_STATUSES",
    "VALID_STATUSES",
    "validate_tracker_fields",
    "validate_tracker_schema",
]

if TYPE_CHECKING:
    from .workspace_tracker import TrackerData

TRACKER_SCHEMA_VERSION = "2.0.0"

VALID_APPROVAL_STATUSES: frozenset[str] = frozenset({
    "not_requested", "pending", "approved", "revision_requested", "rejected",
})

VALID_STATUSES: frozenset[str] = frozenset({
    "pending", "spec_created", "rejected", "approved",
    "requirements_created", "requirements_approved",
    "design_created", "design_approved", "tasks_created",
    "in_progress", "blocked", "failed", "completed", "cancelled",
})


def validate_tracker_fields(data: TrackerData) -> list[str]:
    """Return warning messages for invalid field values in tracker data."""
    warnings_list: list[str] = []
    for sub in data.get("subSpecs", []):
        repo_id = sub.get("repoId", "?")
        status = sub.get("status")
        if status and status not in VALID_STATUSES:
            warnings_list.append(
                f"Sub-spec '{repo_id}' has unknown status '{status}'"
            )
        for doc in DOC_NAMES:
            approval = sub.get("approvals", {}).get(doc, {})
            a_status = approval.get("status")
            if a_status and a_status not in VALID_APPROVAL_STATUSES:
                warnings_list.append(
                    f"Sub-spec '{repo_id}' doc '{doc}' "
                    f"has unknown approval status '{a_status}'"
                )
    return warnings_list


def validate_tracker_schema(data: TrackerData, *, strict: bool = False) -> TrackerData:
    """Check schemaVersion and field values on loaded tracker data.

    When *strict* is True, raises ``ValueError`` on schema mismatch.
    When *strict* is False (default), emits warnings.
    Returns *data* unchanged for chaining.
    """
    if not data:
        return data
    schema_ver = data.get("schemaVersion")
    if schema_ver and schema_ver != TRACKER_SCHEMA_VERSION:
        msg = (
            f"workspace-tracker.json schemaVersion '{schema_ver}' does not "
            f"match expected '{TRACKER_SCHEMA_VERSION}'. "
            f"Tracker may need migration."
        )
        if strict:
            raise ValueError(msg)
        output.warn(msg)
        _warnings.warn(msg, stacklevel=2)
    field_warnings = validate_tracker_fields(data)
    if field_warnings:
        for w in field_warnings:
            output.warn(w)
            _warnings.warn(w, stacklevel=2)
    return data
