#!/usr/bin/env python3
"""Delete a resolved (non-pending) approval.

Usage:
    delete.py --approval-id ID
    delete.py --approval-path PATH         (canonical form)
    delete.py PATH                          (positional shorthand)

Compat flags --category / --target-name are accepted and echoed in
``ignored_flags`` so the agent sees the callout in the JSON envelope.
"""
import _bootstrap  # noqa: F401

import os
from sdd_core import paths, approvals, output, cli
from sdd_core.approval import parse_and_resolve
from sdd_core.harness import load_adapter

def main():
    parser = cli.strict_parser("Delete resolved approval")
    _args, ctx = parse_and_resolve(
        parser,
        required_fields=("approval_id", "approval_path"),
        accept_path_positional=True,
    )
    approval_id = ctx.approval_id
    if not approval_id:
        output.error(
            "approval id is required",
            hint="Pass --approval-id <id> or --approval-path <path>",
        )

    root = paths.require_workflow_root()

    approvals_root = paths.approvals_dir(root)
    result = approvals.find_approval_by_id(approvals_root, approval_id)
    if not result:
        output.error(f"Approval not found: {approval_id}", hint="Check the approval ID")

    fpath, data = result
    if data.get("status") == "pending":
        output.error(
            f"Cannot delete pending approval: {approval_id}",
            hint="Wait for approval/rejection before deleting",
        )

    os.remove(fpath)
    payload = {
        "deletedApprovalId": approval_id,
        "title": data.get("title"),
        "category": data.get("category"),
        "categoryName": data.get("categoryName"),
    }
    if ctx.ignored_flags:
        payload["ignored_flags"] = ctx.ignored_flags

    adapter = load_adapter()
    reconcile_call = adapter.build_residue_reconcile_call()
    if reconcile_call is not None:
        payload["required_tool_calls"] = [reconcile_call]
        payload["required_tool_calls_reason"] = (
            "End of skill run \u2014 reconcile any residual "
            "in_progress / pending tasks before emitting the hand-off "
            "message. See review-approval-pipeline.md \u00a7 Pending "
            "Tool Calls Enforcement."
        )

    output.success(payload, f"Approval {approval_id} deleted successfully")

if __name__ == "__main__":
    cli.run_main(main)
