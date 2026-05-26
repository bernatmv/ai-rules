#!/usr/bin/env python3
"""Print the canonical assessment-staging JSON path for a review target.

Delegates to ``review.pipeline_phases.resolvers.resolve_staging_path`` so
the output matches the sub-agent launcher's injected path exactly.

Usage:
  review_quality/print-staging-path.py --category steering
  review_quality/print-staging-path.py --category spec --target-name my-spec
  review_quality/print-staging-path.py --category discovery --target-name my-feat
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, output, paths as _sdd_paths
from sdd_core.category_registry import (
    REVIEW_TYPE_TO_CATEGORY,
    known_categories,
    review_types,
)
from review.pipeline_phases.resolvers import resolve_staging_path

__sdd_manifest__ = {
    "summary": "Print canonical staging path for a review target",
    "verbs": [
        "--category {spec|steering|prd|discovery}",
    ],
    "flags": ["--category", "--target-name", "--workspace"],
}

# Accept both the reviewer-facing review types (``prd`` alias) and the
# raw pipeline categories (``discovery``) so callers migrating from
# either vocabulary resolve the same staging path.
_CATEGORIES = tuple(sorted(set(review_types()) | set(known_categories())))


def main() -> None:
    parser = cli.strict_parser(__doc__ or "")
    parser.add_argument(
        "--category", required=True, choices=_CATEGORIES,
        help="Review category (prd is an alias for discovery).",
    )
    parser.add_argument(
        "--target-name", default="",
        type=cli.name_type("target-name"),
        help=(
            "Spec / discovery target name. Optional for --category "
            "steering; required otherwise."
        ),
    )
    parser.add_argument(
        "--gate-id", default="",
        help=(
            "Gate id for per-gate addressable staging "
            "(``review-assessment-staging-<gate_id>.json``). Omit to "
            "return the gate-id-less filename for entry-style phases "
            "that have no gate context."
        ),
    )
    args = parser.parse_args()

    if args.category != "steering" and not args.target_name:
        output.error(
            "--target-name is required for non-steering categories",
            hint=(
                "Pass --target-name <spec-or-feature-name>. "
                "Steering reviews are repo-global and accept an empty target."
            ),
            next_action_command=(
                ".spec-workflow/sdd review_quality/print-staging-path.py "
                f"--category {args.category} --target-name <name>"
            ),
        )

    category = REVIEW_TYPE_TO_CATEGORY.get(args.category, args.category)
    project_path = _sdd_paths.resolve_project_path(args)

    path = resolve_staging_path(
        category, args.target_name, project_path,
        gate_id=args.gate_id or "",
    )
    output.success(
        {
            "category": args.category,
            "target_name": args.target_name,
            "gate_id": args.gate_id or "",
            "staging_path": path,
        },
        f"Canonical staging path for {args.category}: {path}",
    )


if __name__ == "__main__":
    cli.run_main(main)
