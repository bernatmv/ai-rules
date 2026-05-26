#!/usr/bin/env python3
"""Validate a review-quality.json artifact for completeness.

Usage:
  validate-review-artifact.py --category spec --target-name <name>
  validate-review-artifact.py --spec-path <path-to-review-quality.json>

Checks:
  - File exists and is valid JSON
  - last_full_review_at is non-null
  - overall_status is not INCOMPLETE
  - Each reviewed document has integer line_count

Exit codes: 0 valid, 1 invalid (with diagnostic message).
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import os

from sdd_core import cli, handoffs, output, paths
from sdd_core.paths import doc_dir_path


def validate(spec_path: str) -> list[str]:
    """Return a list of validation errors (empty = valid)."""
    errors: list[str] = []

    if not os.path.isfile(spec_path):
        return [f"File not found: {spec_path}"]

    try:
        data = output.safe_read_json(spec_path)
    except ValueError as e:
        return [str(e)]
    if data is None:
        return [f"File not found: {spec_path}"]

    if data.get("last_full_review_at") is None:
        errors.append(
            "last_full_review_at is null — the full review workflow was not completed"
        )

    status = data.get("overall_status", "INCOMPLETE")
    if status == "INCOMPLETE":
        errors.append("overall_status is INCOMPLETE — expected PASS or NEEDS_WORK")

    docs = data.get("documents", {})
    for doc_key, doc_data in docs.items():
        if not isinstance(doc_data, dict):
            continue
        if doc_data.get("status") == "INCOMPLETE":
            continue
        line_count = doc_data.get("line_count")
        if line_count is None or not isinstance(line_count, int):
            errors.append(
                f"documents.{doc_key}.line_count is {line_count!r} — expected integer"
            )

    return errors


def main() -> None:
    parser = cli.strict_parser(
        "Validate a review-quality.json artifact for completeness",
    )
    # Two equivalent ways to locate the artifact: pass --spec-path
    # directly, or use the shared --category / --target-name locator so
    # the script resolves the artifact path internally.
    cli.add_document_selectors(
        parser, spec_name=True, category=True,
    )
    parser.add_argument(
        "--spec-path", default=None,
        help="Path to review-quality.json",
    )
    parser.add_argument(
        "--strict-presence", action="store_true",
        help=(
            "Treat missing artifact as `output.preflight_required` "
            "(exit 0) instead of `output.error` (exit 1). Malformed "
            "artifacts still error. Used by W4 review-gate enforcement."
        ),
    )
    args = parser.parse_args()

    spec_path = args.spec_path
    if not spec_path:
        if args.category and args.spec_name:
            project_root = paths.resolve_project_path(args)
            doc_directory = doc_dir_path(args.category, args.spec_name, project_root)
            spec_path = os.path.join(doc_directory, "review-quality.json")
        else:
            parser.error(
                "Either --spec-path or --category + --target-name is required"
            )

    if args.strict_presence and not os.path.isfile(spec_path):
        output.preflight_required(
            {
                "path": spec_path,
                "gate": "review-artifact-required",
            },
            f"review-quality artifact missing: {spec_path}",
            next_action_command=(
                f".spec-workflow/sdd review/validate-review-artifact.py "
                f"--spec-path {spec_path} --strict-presence"
            ),
            hint="Run sdd-review-spec-docs to produce the artifact, then re-run.",
        )

    errors = validate(spec_path)
    if errors:
        output.error(
            "; ".join(errors),
            hint="Re-run the review skill to produce a complete artifact",
            exit_code=1,
        )

    # Surface the same finding-count contract every post-review envelope
    # carries so consumers (post-review re-run, gate-aware tooling) can
    # branch on a single source of truth.
    from review_quality.findings import count_findings_in_artifact
    artifact = output.safe_read_json(spec_path) or {}
    findings_count = count_findings_in_artifact(artifact)
    handoff_ctx = {
        "workspace": getattr(args, "workspace", "") or ".",
        "target": args.spec_name or "",
        "phase": getattr(args, "doc", "") or "",
        "category": args.category or "",
    }
    output.success(
        {
            "path": spec_path,
            "valid": True,
            "findings_count": findings_count,
            "findings_present": findings_count > 0,
        },
        f"Artifact valid: {spec_path}",
        handoffs=handoffs.handoffs_for(
            handoffs.current_script_id(), handoff_ctx,
        ),
    )


if __name__ == "__main__":
    cli.run_main(main)
