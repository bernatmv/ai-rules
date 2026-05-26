#!/usr/bin/env python3
"""Archive or unarchive a spec.

Usage: archive-spec.py --target NAME --action (archive|unarchive|status)
"""

import _bootstrap  # noqa: F401

import shutil

from sdd_core import paths, output, cli, handoffs

# Mirrors workflow-graph.json `sdd-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def main():
    parser = cli.strict_parser("Archive/unarchive spec")
    cli.target_argument(parser, family="spec")
    parser.add_argument("--action", required=True, choices=["archive", "unarchive", "status"])
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    root = paths.require_workflow_root()

    active = paths.spec_dir(root, args.spec_name)
    archived = paths.archive_dir(root, args.spec_name)

    def _emit(payload: dict, msg: str) -> None:
        output.success(
            payload,
            msg,
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )

    if args.action == "status":
        if active.is_dir():
            _emit({"specName": args.spec_name, "location": "active", "path": str(active)}, "Spec is active")
        elif archived.is_dir():
            _emit({"specName": args.spec_name, "location": "archived", "path": str(archived)}, "Spec is archived")
        else:
            output.error(f"Spec not found: {args.spec_name}", hint="Check spec name with spec/check-status.py --all")

    elif args.action == "archive":
        if not active.is_dir():
            output.error(f"Active spec not found: {args.spec_name}")
        if archived.is_dir():
            output.error(f"Archive target already exists: {archived}")
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(active), str(archived))
        _emit({"specName": args.spec_name, "action": "archived", "from": str(active), "to": str(archived)}, f"Spec {args.spec_name} archived")

    elif args.action == "unarchive":
        if not archived.is_dir():
            output.error(f"Archived spec not found: {args.spec_name}")
        if active.is_dir():
            output.error(f"Active spec already exists: {active}")
        active.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(archived), str(active))
        _emit({"specName": args.spec_name, "action": "unarchived", "from": str(archived), "to": str(active)}, f"Spec {args.spec_name} unarchived")

if __name__ == "__main__":
    cli.run_main(main)
