#!/usr/bin/env python3
"""Create document snapshot or compare snapshot versions.

Usage: create-snapshot.py --file-path PATH --approval-id ID --approval-title TITLE --trigger TRIGGER --status STATUS
       create-snapshot.py --compare --category-name CAT --file-name FILE --snapshot-a N --snapshot-b N
"""

import _bootstrap  # noqa: F401

from sdd_core import paths, snapshots, output, cli, handoffs
from pathlib import Path

# Snapshots are taken in any spec workflow phase; mirror
# `sdd-create-spec.context_needs` so the resolver records workspace +
# the active target/category in the success envelope.
__sdd_context_needs__ = ("target", "workspace", "category")


def main() -> None:
    parser = cli.strict_parser("Create or compare snapshots")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--file-path")
    parser.add_argument("--approval-id", type=cli.name_type("approval-id"))
    parser.add_argument("--approval-title")
    parser.add_argument("--trigger", choices=["initial", "revision_requested", "approved", "manual"])
    parser.add_argument("--status")
    parser.add_argument("--category-name", type=cli.name_type("target-name"))
    parser.add_argument("--file-name")
    parser.add_argument("--snapshot-a", type=int)
    parser.add_argument("--snapshot-b", type=int)
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    root = paths.require_workflow_root()

    def _emit(payload: dict, msg: str) -> None:
        output.success(
            payload,
            msg,
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )

    if args.compare:
        if not all([args.category_name, args.file_name, args.snapshot_a is not None, args.snapshot_b is not None]):
            output.error("--compare requires --category-name, --file-name, --snapshot-a, --snapshot-b")
        snap_dir = paths.snapshots_dir(root, args.category_name, args.file_name)
        try:
            result = snapshots.compare_snapshots(snap_dir, args.snapshot_a, args.snapshot_b)
        except FileNotFoundError as e:
            output.error(str(e))
        _emit(result, f"Compared v{args.snapshot_a} vs v{args.snapshot_b}")
    else:
        if not all([args.file_path, args.approval_id, args.approval_title, args.trigger, args.status]):
            output.error("Create mode requires --file-path, --approval-id, --approval-title, --trigger, --status")
        full_path = root / args.file_path
        snap_dir = paths.snapshots_dir(root, args.category_name or "", Path(args.file_path).name)
        snap = snapshots.create_snapshot(full_path, args.approval_id, args.approval_title, args.trigger, args.status, snap_dir, canonical_path=args.file_path)
        _emit({"snapshotId": snap["id"], "version": snap["version"], "path": str(snap_dir)}, "Snapshot created")

if __name__ == "__main__":
    cli.run_main(main)
