"""Test helpers for convention enforcement across all script tests."""
from __future__ import annotations

import json

from .output import (
    VALID_STDOUT_STATUSES,
    VALID_STDERR_STATUSES,
    STDOUT_REQUIRED_FIELDS,
    STDERR_REQUIRED_FIELDS,
)

__all__ = [
    "assert_script_output_format",
    "assert_script_error_format",
]


def _assert_envelope(raw: str, valid_statuses: frozenset[str],
                     required_fields: dict[str, tuple[str, ...]]) -> None:
    """Validate a JSON envelope against status and required-field constraints."""
    data = json.loads(raw)
    assert "status" in data, "Missing 'status' field in output"
    status = data["status"]
    assert status in valid_statuses, f"Invalid status: {status}"
    for field in required_fields.get(status, ()):
        assert field in data, f"Missing '{field}' field in {status} response"


def assert_script_output_format(stdout: str) -> None:
    """Validate script output matches the standard JSON envelope (StdoutResponse)."""
    _assert_envelope(stdout, VALID_STDOUT_STATUSES, STDOUT_REQUIRED_FIELDS)


def assert_script_error_format(stderr: str) -> None:
    """Validate error output matches convention."""
    try:
        _assert_envelope(stderr, VALID_STDERR_STATUSES, STDERR_REQUIRED_FIELDS)
    except json.JSONDecodeError:
        assert stderr.startswith("Error:"), (
            f"Non-JSON error must start with 'Error:': {stderr[:50]}"
        )
