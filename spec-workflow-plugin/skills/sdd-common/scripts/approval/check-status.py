#!/usr/bin/env python3
"""Check approval status by ID or category name.

Usage: check-approval-status.py (--approval-id ID | --category-name NAME)
"""
import _bootstrap  # noqa: F401

from sdd_core import paths, approvals, output, cli

def main():
    parser = cli.strict_parser("Check approval status")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--approval-id", type=cli.name_type("approval-id"))
    group.add_argument("--category-name", type=cli.name_type("target-name"))
    args = parser.parse_args()

    root = paths.require_workflow_root()

    approvals_root = paths.approvals_dir(root)

    if args.approval_id:
        result = approvals.find_approval_by_id(approvals_root, args.approval_id)
        if not result:
            output.error(f"Approval not found: {args.approval_id}", hint="Check the approval ID")
        _, data = result
        output.success(data, f"Approval status: {data.get('status')}")
    else:
        results = approvals.scan_approvals(approvals_root, category=None, status_filter=None)
        filtered = [a for a in results if a.get("categoryName") == args.category_name]
        if not filtered:
            output.error(f"No approvals found for: {args.category_name}", hint="Check the category name")
        output.success({"approvals": filtered, "count": len(filtered)}, f"{len(filtered)} approval(s) for {args.category_name}")

if __name__ == "__main__":
    cli.run_main(main)
