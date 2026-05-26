#!/usr/bin/env python3
"""Create a new approval request with initial snapshot.

Usage: request.py --title TITLE --file-paths "a.md,b.md" --type TYPE --category CAT --target-name NAME
"""
import _bootstrap  # noqa: F401

import argparse
from pathlib import Path

from sdd_core import paths, approvals, snapshots, output, cli, command_templates
from sdd_core.reference_ledger import hash_file
from sdd_core.time import ts_now


# Initial approval status — every approval row starts here so update-status.py's
# pending-only invariant has a single source of truth for the source state.
APPROVAL_STATUS_PENDING = "pending"
# Verification block state when content_hash is fresh; future drift toggles to "stale".
VERIFICATION_STATE_CURRENT = "current"
# Snapshot trigger label for the very first capture taken at request time.
SNAPSHOT_TRIGGER_INITIAL = "initial"
# Hash algorithm prefix on contentHash so the gate can swap algorithms by value.
CONTENT_HASH_ALGORITHM_PREFIX = "sha256:"


def main() -> None:
    parser = cli.strict_parser("Create approval request")
    parser.add_argument("--title", required=True)
    parser.add_argument("--file-paths", required=True, help="Comma-separated file paths")
    parser.add_argument("--type", required=True, choices=["document", "action"])
    parser.add_argument("--category", required=True, choices=approvals.APPROVAL_CATEGORIES)
    parser.add_argument("--target-name", dest="category_name",
                        type=cli.name_type("target-name"),
                        help="Name of the spec, steering doc, or discovery project")
    parser.add_argument("--category-name", dest="category_name",
                        type=cli.name_type("target-name"),
                        help=argparse.SUPPRESS)
    args = parser.parse_args()

    if not args.category_name:
        output.error("--target-name is required",
                     hint="Example: --target-name my-feature-name")

    root = paths.require_workflow_root()

    all_paths = [p.strip() for p in args.file_paths.split(",") if p.strip()]

    primary_path = all_paths[0]

    for fp in all_paths:
        try:
            paths.validate_path(fp, root)
        except ValueError as e:
            output.error(str(e), hint="Use a relative path within the project")

        full_path = root / fp
        if full_path.is_dir():
            output.error(
                f"--file-paths must reference files, not directories: {fp}",
                hint="Use the primary document path (e.g., requirements.md) for package approvals.",
            )
        if not full_path.exists():
            output.error(f"File not found: {fp}", hint="Create the document before requesting approval")

    approval_id = approvals.create_approval_id()
    now = ts_now()
    canonical = (root / primary_path).resolve(strict=True)
    content_hash = f"{CONTENT_HASH_ALGORITHM_PREFIX}{hash_file(canonical)}"
    approval_data = {
        "id": approval_id,
        "title": args.title,
        # filePath retained for single-file consumers and attribution.
        "filePath": primary_path,
        "filePaths": all_paths,
        "type": args.type,
        "status": APPROVAL_STATUS_PENDING,
        "createdAt": now,
        "category": args.category,
        "categoryName": args.category_name,
        # Security hardening identity tuple — canonical absolute path
        # plus the bytes-at-request-time content hash. The gate re-hashes
        # at approve-time and refuses drifted bytes.
        "canonicalPath": str(canonical),
        "contentHash": content_hash,
        "verification": {
            "state": VERIFICATION_STATE_CURRENT,
            "lastVerifiedAt": now,
            "lastHash": content_hash,
            "reason": "",
        },
        # Reserved for future GPG/SSH signature proof (H1 seam).
        "authorizedBy": None,
    }

    approval_path = paths.approvals_dir(root, args.category_name) / f"{approval_id}.json"
    approvals.write_approval(approval_path, approval_data)

    primary_full = root / primary_path
    snap_dir = paths.snapshots_dir(root, args.category_name, Path(primary_path).name)
    snap = snapshots.create_snapshot(primary_full, approval_id, args.title, SNAPSHOT_TRIGGER_INITIAL, APPROVAL_STATUS_PENDING, snap_dir, canonical_path=primary_path)

    approval_file_relative = str(approval_path.relative_to(root))
    commands_suite = command_templates.build_request_commands_suite(
        approval_id=approval_id,
        file_path=approval_file_relative,
    )

    output.success({
        "approvalId": approval_id,
        "approvalFilePath": approval_file_relative,
        # filePath retained for legacy single-file consumers.
        "filePath": primary_path,
        "filePaths": all_paths,
        "status": APPROVAL_STATUS_PENDING,
        "snapshotVersion": snap["version"],
        "commands_suite": commands_suite,
    }, "Approval request created successfully")

if __name__ == "__main__":
    cli.run_main(main)
