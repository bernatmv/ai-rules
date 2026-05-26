#!/usr/bin/env python3
"""Write or delete progressive PRD session state.

Usage:
    write-session-state.py --target <name> --step <1-5> --data <json-string>
    write-session-state.py --target <name> --step <1-5> --show-schema
    write-session-state.py --target <name> --delete

Writes or updates .spec-workflow/discovery/{feature}/.prd-session.json.
Uses atomic write (tempfile + os.replace) consistent with sdd_core conventions.

Exit codes:
    0 — success (updated, deleted, or schema printed)
    1 — validation error (missing required fields for the declared step)
    2 — usage error
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
import os
from datetime import datetime, timezone

from sdd_core import cli, handoffs, output
from prd import session_validators

# Mirrors workflow-graph.json `sdd-create-prd.context_needs`.
__sdd_context_needs__ = ("target", "workspace")

SCHEMA_VERSION = "1.0.0"

STEP_SCHEMAS: dict[int, str] = {
    1: '{"problem_statement": {"text": "<2+ sentences describing the problem>"}}',
    2: '{"goals": [{"id": "G1", "goal": "...", "metric": "...", "target": "...", "measurement_method": "..."}]}  # min 2 goals',
    3: '{"in_scope": [...], "out_of_scope": [...], "non_goals": [{"id": "NG1", "statement": "...", "reason": "..."}], "deferred": [...]}',
    4: '{"requirements": [{"id": "FR-1", "priority": "P0", "text": "WHEN ... THEN ..."}], "nfr_categories": {"performance": "...", "availability": "...", "scalability": "...", "security": "...", "data_consistency": "...", "observability": "..."}}',
    5: '{"stress_test": {"objections": [{"id": "EP-1", "objection": "...", "reference": "...", "resolution": "..."}], "objections_resolved": true, "ryg": {...}, "ryg_reds": [], "ryg_notes": "..."}}',
}

REQUIRED_FIELDS: dict[int, list[tuple[str, ...]]] = {
    1: [("problem_statement", "text")],
    2: [("goals",)],
    3: [("non_goals",)],
    4: [("requirements",), ("nfr_categories",)],
    5: [("stress_test", "objections_resolved"), ("stress_test", "ryg_reds")],
}

# Fields where empty lists are valid — business-rule validators handle semantics
EMPTY_LIST_DELEGATED: set[tuple[str, ...]] = {
    ("stress_test", "ryg_reds"),
}


def _get_nested(data: dict, keys: tuple[str, ...]):
    """Walk a nested dict by key path. Returns None on missing key."""
    val = data
    for key in keys:
        if not isinstance(val, dict):
            return None
        val = val.get(key)
        if val is None:
            return None
    return val


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge *overlay* into *base*, returning a new dict."""
    result = base.copy()
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _session_path(feature_name: str) -> str:
    from sdd_core.paths import WORKFLOW_DIR
    return os.path.join(
        WORKFLOW_DIR, "discovery", feature_name, ".prd-session.json"
    )


def _validate_step(step: int, data: dict) -> list[str]:
    """Presence checks (structural) + delegated business-rule validation."""
    gaps = []
    for key_path in REQUIRED_FIELDS.get(step, []):
        value = _get_nested(data, key_path)
        dotted = ".".join(key_path)
        if value is None:
            gaps.append(f"Step {step} requires '{dotted}'")
        elif isinstance(value, str) and not value.strip():
            gaps.append(f"'{dotted}' is empty")
        elif isinstance(value, list) and len(value) == 0 and key_path not in EMPTY_LIST_DELEGATED:
            gaps.append(f"'{dotted}' has no entries")
    gaps.extend(session_validators.validate_step(step, data))
    return gaps


def main() -> None:
    parser = cli.strict_parser("Write or delete PRD session state")
    cli.target_argument(parser, family="prd")
    parser.add_argument("--step", type=int, choices=range(1, 6),
                        help="Step number (1-5)")
    parser.add_argument("--data", help="JSON string with session data for this step")
    parser.add_argument("--delete", action="store_true",
                        help="Delete the session state file")
    parser.add_argument("--show-schema", action="store_true",
                        help="Print expected JSON schema for --step and exit")
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    def _emit(payload: dict, msg: str) -> None:
        output.success(
            payload,
            msg,
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )

    if args.show_schema:
        if args.step is None:
            output.error("--show-schema requires --step")
        schema = STEP_SCHEMAS.get(args.step)
        if schema is None:
            output.error(f"No schema defined for step {args.step}")
        _emit(
            {"step": args.step, "schema": schema},
            f"Expected JSON schema for step {args.step}",
        )
        return

    session_file = _session_path(args.feature)

    if args.delete:
        if os.path.isfile(session_file):
            os.remove(session_file)
            _emit(
                {"deleted": True, "path": session_file},
                "Session state deleted",
            )
        else:
            _emit(
                {"deleted": False, "path": session_file},
                "No session state file to delete",
            )
        return

    if args.step is None or args.data is None:
        output.error(
            "Both --step and --data are required when not using --delete",
        )

    try:
        new_data = json.loads(args.data)
    except json.JSONDecodeError as e:
        output.error(f"Invalid JSON in --data: {e}")

    gaps = _validate_step(args.step, new_data)
    if gaps:
        output.error(
            f"Validation failed for step {args.step}: {len(gaps)} issue(s)",
            hint="Provide the required fields for this step",
            context="\n".join(f"- {g}" for g in gaps),
        )

    existing = output.safe_read_json(session_file, default={})

    existing = _deep_merge(existing, new_data)
    existing["schema_version"] = SCHEMA_VERSION
    existing["feature_name"] = args.feature
    existing["current_step"] = args.step
    existing["updated_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    output.atomic_write_json(session_file, existing)
    _emit(existing, f"Session state updated (step {args.step})")


if __name__ == "__main__":
    cli.run_main(main)
