#!/usr/bin/env python3
"""Detect if a spec name indicates a bug fix.

Usage: detect-type.py <spec-name>  |  detect-type.py --target <spec-name>
Exit code: 0 = success, 1 = error / usage error.
Output: JSON with data.type = "bug-fix" or "standard".
"""

import _bootstrap  # noqa: F401

from sdd_core import cli, handoffs, output
from sdd_core.specs import is_bug_fix_spec

# Mirrors workflow-graph.json `sdd-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("spec_name_pos", nargs="?", default=None, help="Spec name to classify")
    cli.target_argument(parser, family="spec", required=False)
    args = parser.parse_args()
    args.spec_name = args.spec_name or args.spec_name_pos
    if not args.spec_name:
        output.error("Spec name is required (positional or --target)")
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    spec_type = "bug-fix" if is_bug_fix_spec(args.spec_name) else "standard"
    output.success(
        {"type": spec_type},
        f"Spec type: {spec_type}",
        ctx=ctx,
        resolved_from=dict(ctx.resolved_from),
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


if __name__ == "__main__":
    cli.run_main(main)
