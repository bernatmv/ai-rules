#!/usr/bin/env python3
"""List pending approval requests from .spec-workflow/approvals/.

Usage: list-pending.py [--category spec|steering|discovery] [--target <name>] [--approvals-dir <dir>]
Output: JSON array on stdout, human summary on stderr.
Exit code: 0 always (a search miss is `data.outcome="miss"`, not exit 1).
"""

import _bootstrap  # noqa: F401

from pathlib import Path

from sdd_core import approvals as _approvals, output, cli
from sdd_core.paths import WORKFLOW_DIR


def main() -> None:
    parser = cli.strict_parser("List pending approval requests")
    parser.add_argument("--category", choices=_approvals.APPROVAL_CATEGORIES, help="Filter by category")
    cli.target_argument(parser, family="spec", required=False)
    parser.add_argument("--approvals-dir", help="Override approvals directory path")
    args = parser.parse_args()

    filter_category = args.category
    filter_spec = args.spec_name
    approvals_path = Path(args.approvals_dir) if args.approvals_dir else Path(WORKFLOW_DIR) / "approvals"

    if not approvals_path.is_dir():
        output.miss(
            {"approvals": [], "count": 0, "approvals_dir": str(approvals_path)},
            f"No approvals directory found at {approvals_path}",
        )

    pending = _approvals.scan_approvals(
        approvals_path,
        category=filter_category,
        status_filter="pending",
        warn_callback=output.warn,
    )

    if filter_spec:
        pending = [a for a in pending if a.get("categoryName") == filter_spec]

    # filePath retained for legacy single-file consumers; new callers
    # should read ``filePaths`` from the approval record directly.
    results = [
        {
            "id": a.get("id"),
            "title": a.get("title"),
            "filePath": a.get("filePath"),
            "category": a.get("category"),
            "categoryName": a.get("categoryName"),
            "createdAt": a.get("createdAt"),
            "_source_file": a.get("_source_file"),
        }
        for a in pending
    ]

    if not results:
        output.miss(
            {"approvals": [], "count": 0},
            "No pending approvals found",
        )

    output.success({"approvals": results, "count": len(results)}, f"{len(results)} pending approval(s) found")


if __name__ == "__main__":
    cli.run_main(main)
