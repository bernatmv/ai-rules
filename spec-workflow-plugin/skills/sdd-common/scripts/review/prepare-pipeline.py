#!/usr/bin/env python3
"""Prepare review pipeline: generate sub-agent prompts and manage fix cycles.

Each pipeline phase owns its own flags, help text, and entry-point
validator. Run ``prepare-pipeline.py <phase> --help`` for the phase-
scoped flag set.

Usage:
  prepare-pipeline.py launch \\
    --review-skill sdd-review-steering-docs \\
    --workspace . --doc-list "product.md" \\
    --category steering --scope per-document

  prepare-pipeline.py check-revalidation \\
    --doc product.md --target-name steering \\
    --category steering --fix-cycle 1 --max-cycles 2

  prepare-pipeline.py post-fix \\
    --doc-list "product.md,structure.md" --target-name steering \\
    --category steering --fix-cycle 1 --max-cycles 2

  prepare-pipeline.py pre-approval \\
    --doc-list "product.md,tech.md,structure.md" --target-name steering \\
    --category steering

Exit code: 0 always (result in JSON envelope).
"""
import _bootstrap  # noqa: F401

import argparse

from sdd_core import cli
import review.pipeline_phases  # noqa: F401 — fires @phase decorators
from review.phase_kit import bind_to_prepare_pipeline


def _build_common_parser() -> argparse.ArgumentParser:
    """Return the parent parser every sub-parser inherits from.

    Carries the flags shared by every phase: ``--workspace``,
    ``--category``, ``--target-name`` (with ``--spec-name`` alias),
    and the lifecycle trio (``--parent-todo`` /
    ``--parent-todo-content`` / ``--gate-id``). Hoisting the lifecycle
    flags onto the common parent parser makes the blanket "pass these
    flags to all phase calls" guidance literally true — no phase's
    argparse can reject them. ``add_help=False`` so the subparser can
    advertise its own help.
    """
    common = cli.strict_parser(__doc__, add_help=False)
    common.add_argument(
        "--category", default="spec",
        choices=("spec", "steering", "discovery"),
        help="Approval category",
    )
    common.add_argument(
        "--target-name", "--spec-name", default="",
        dest="target_name",
        type=cli.name_type("target-name"),
        help="Spec name, steering name, or discovery project name",
    )
    common.add_argument(
        "--parent-todo", default=None,
        help="Parent TODO id for fix-loop lifecycle tracking",
    )
    common.add_argument(
        "--parent-todo-content", default=None,
        help=(
            "Verbatim content of the agent's parent TODO. "
            "Persisted on the review_gate so pipeline-emitted "
            "TodoWrite payloads can preserve the original phrasing."
        ),
    )
    common.add_argument(
        "--gate-id", default=None,
        help="Gate id for multi-gate safety (e.g. step3)",
    )
    return common


def main() -> None:
    common = _build_common_parser()
    parser = cli.strict_parser(
        __doc__, epilog=(
            "Examples:\n"
            "  Launch:\n"
            "    prepare-pipeline.py launch --review-skill sdd-review-spec-docs \\\n"
            '      --workspace . --doc-list "requirements.md" --category spec --target-name my-feature\n'
            "  Check revalidation:\n"
            "    prepare-pipeline.py check-revalidation --workspace . \\\n"
            "      --category spec --target-name my-feature --doc requirements.md\n"
            "  Pre-approval:\n"
            "    prepare-pipeline.py pre-approval --workspace . \\\n"
            '      --category spec --target-name my-feature --doc-list "requirements.md"\n'
        ),
        parents=[common], workspace=False,
    )
    subs = parser.add_subparsers(dest="phase", required=True)
    # Single dispatch authority: every phase is wired via its
    # ``@phase`` decorator plus :meth:`Phase.register`. The
    # ``import review.pipeline_phases`` above triggered every decorator
    # through the package ``__init__.py`` side-effect loop.
    bind_to_prepare_pipeline(subs, common)

    args = parser.parse_args()
    args._handler(args)


if __name__ == "__main__":
    cli.run_main(main)
