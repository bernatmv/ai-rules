#!/usr/bin/env python3
"""Clean up old resolved approvals.

Usage: cleanup-approvals.py [--max-age-days N] [--dry-run]
"""
import _bootstrap  # noqa: F401

import os
from sdd_core import paths, approvals, output, cli
from sdd_core.approvals import RESOLVED_STATUSES

def main():
    parser = cli.strict_parser("Clean up old approvals")
    parser.add_argument("--max-age-days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = paths.require_workflow_root()

    approvals_root = paths.approvals_dir(root)
    all_approvals = approvals.scan_approvals(approvals_root)

    non_pending = [a for a in all_approvals if a.get("status") in RESOLVED_STATUSES]
    pending = [a for a in all_approvals if a.get("status") not in RESOLVED_STATUSES]

    expired, current = approvals.filter_by_age(non_pending, args.max_age_days)

    deleted = []
    preserved = [{"id": a.get("id"), "status": a.get("status")} for a in current]
    skipped_pending = [{"id": a.get("id"), "title": a.get("title")} for a in pending]

    for a in expired:
        source = a.get("_source_file")
        if source and os.path.exists(source):
            if not args.dry_run:
                os.remove(source)
            deleted.append({"id": a.get("id"), "status": a.get("status"), "createdAt": a.get("createdAt")})

    mode = " (dry run)" if args.dry_run else ""
    output.success({
        "deleted": deleted,
        "preserved": preserved,
        "skipped_pending": skipped_pending,
    }, f"Cleanup complete{mode}: {len(deleted)} deleted, {len(preserved)} preserved, {len(skipped_pending)} pending skipped")

if __name__ == "__main__":
    cli.run_main(main)
