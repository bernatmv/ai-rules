#!/usr/bin/env python3
"""Manage code review progress state with multi-phase CLI.

Phases:
    record      — Record one dimension's completion (after each Step 4x)
    conventions — Record convention discovery summary (after Step 3)
    check       — Validate all required dimensions complete (before Step 6)
    reset       — Clear state for a new review

State file: .spec-workflow/.review-progress.json
    Written atomically via output.atomic_write_json().

Usage:
    .spec-workflow/sdd review/validate-review-progress.py \\
        --phase record --dimension code_quality --read-file --checks-cited 3
    .spec-workflow/sdd review/validate-review-progress.py \\
        --phase conventions --summary "ESLint flat config, Prettier, 2-space indent"
    .spec-workflow/sdd review/validate-review-progress.py --phase check
    .spec-workflow/sdd review/validate-review-progress.py --phase reset
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import os

from sdd_core import cli, output
from sdd_core.time import ts_now
from review.review_config import DIMENSION_KEYS, DIMENSION_LABELS
from sdd_core.validation_helpers import format_error_list
from review_quality.constants import PROGRESS_SCHEMA_VERSION, MIN_CHECKS_CITED

SCHEMA_VERSION = PROGRESS_SCHEMA_VERSION
STATE_FILE = os.path.join(".spec-workflow", ".review-progress.json")

PHASES = ("record", "conventions", "check", "reset")


def validate_progress(data: dict) -> dict:
    """Validate progress data.  Returns a result dict with ``valid`` bool."""
    not_read: list[str] = []
    no_checks: list[str] = []
    missing_dims: list[str] = []

    dims = data.get("dimensions") or {}

    for dim_key in DIMENSION_KEYS:
        label = DIMENSION_LABELS.get(dim_key, dim_key)
        entry = dims.get(dim_key)
        if entry is None:
            missing_dims.append(label)
            continue
        if not entry.get("read_file"):
            not_read.append(label)
        checks = entry.get("checks_cited", 0)
        if not isinstance(checks, int) or checks < MIN_CHECKS_CITED:
            no_checks.append(label)

    conventions_summary = (data.get("conventions_summary") or "").strip()
    conventions_missing = not conventions_summary

    valid = (
        not missing_dims
        and not not_read
        and not no_checks
        and not conventions_missing
    )

    return {
        "valid": valid,
        "missing_dimensions": missing_dims,
        "not_read": not_read,
        "no_checks_cited": no_checks,
        "conventions_summary_missing": conventions_missing,
    }


def _read_state() -> dict:
    data = output.safe_read_json(STATE_FILE)
    return data if isinstance(data, dict) else {}


def _write_state(state: dict) -> None:
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = ts_now()
    output.atomic_write_json(STATE_FILE, state)


def _remaining_dimensions(state: dict) -> list[str]:
    dims = state.get("dimensions") or {}
    return [k for k in DIMENSION_KEYS if k not in dims]


def _build_error_list(result: dict) -> list[str]:
    """Build human-readable error list from validate_progress result."""
    errors: list[str] = []
    if result["missing_dimensions"]:
        errors.append(f"Missing dimensions: {', '.join(result['missing_dimensions'])}")
    if result["not_read"]:
        errors.append(f"Criteria file not read: {', '.join(result['not_read'])}")
    if result["no_checks_cited"]:
        errors.append(f"No checks cited: {', '.join(result['no_checks_cited'])}")
    if result["conventions_summary_missing"]:
        errors.append("conventions_summary is empty — complete Step 3 first")
    return errors


def _phase_record(args) -> None:
    if args.dimension not in DIMENSION_KEYS:
        output.error(
            f"Unknown dimension: {args.dimension}",
            hint=f"Valid dimensions: {', '.join(DIMENSION_KEYS)}",
        )

    if args.checks_cited is None or args.checks_cited < MIN_CHECKS_CITED:
        output.error(
            f"--checks-cited must be >= 1, got {args.checks_cited}",
            hint="Cite at least one specific check from the criteria file",
        )

    state = _read_state()
    dims = state.setdefault("dimensions", {})
    dims[args.dimension] = {
        "read_file": args.read_file,
        "checks_cited": args.checks_cited,
        "recorded_at": ts_now(),
    }
    _write_state(state)

    remaining = _remaining_dimensions(state)
    output.success(
        {
            "dimension": args.dimension,
            "recorded": True,
            "remaining": remaining,
            "remaining_count": len(remaining),
        },
        f"Recorded {DIMENSION_LABELS[args.dimension]}"
        + (f"; {len(remaining)} remaining" if remaining else "; all dimensions recorded"),
    )


def _phase_conventions(args) -> None:
    summary = (args.summary or "").strip()
    if not summary:
        output.error(
            "Convention summary is empty",
            hint="Provide a non-empty --summary from Step 3 convention discovery",
        )

    state = _read_state()
    state["conventions_summary"] = summary
    _write_state(state)

    remaining = _remaining_dimensions(state)
    output.success(
        {
            "conventions_summary": summary,
            "remaining_dimensions": remaining,
            "remaining_count": len(remaining),
        },
        "Conventions summary recorded",
    )


def _phase_check(args) -> None:
    state = _read_state()
    if not state:
        output.error(
            "No progress state found",
            hint="Record dimensions with --phase record before checking",
        )

    result = validate_progress(state)

    if result["valid"]:
        output.success(result, "All required dimensions evaluated")

    output.result(result, format_error_list(_build_error_list(result)), exit_code=1)


def _phase_reset(_args) -> None:
    if os.path.isfile(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except OSError as exc:
            output.error(f"Failed to remove {STATE_FILE}: {exc}")
        output.success({"reset": True, "path": STATE_FILE}, "Progress state cleared")
    else:
        output.success(
            {"reset": False, "path": STATE_FILE},
            "No progress state file to clear",
        )


def main() -> None:
    parser = cli.strict_parser(
        description="Manage code review progress state",
    )
    parser.add_argument(
        "--phase", required=True, choices=PHASES,
        help="Phase: record | conventions | check | reset",
    )
    parser.add_argument(
        "--dimension",
        help="Dimension key to record (required for --phase record)",
    )
    parser.add_argument(
        "--read-file", action="store_true", default=False,
        help="Mark that the criteria file was read",
    )
    parser.add_argument(
        "--checks-cited", type=int,
        help="Number of checks cited from criteria file (required for --phase record)",
    )
    parser.add_argument(
        "--summary",
        help="Convention discovery summary (required for --phase conventions)",
    )
    args = parser.parse_args()

    handlers = {
        "record": _phase_record,
        "conventions": _phase_conventions,
        "check": _phase_check,
        "reset": _phase_reset,
    }
    handlers[args.phase](args)


if __name__ == "__main__":
    cli.run_main(main)
