"""Status transitions, summary calculation, and doc approval logic."""
from __future__ import annotations

from collections import Counter
from typing import Optional, TYPE_CHECKING

from .specs import DOC_NAMES
from . import time as sdd_time
from ._workspace_io import find_by_key

__all__ = [
    "VALID_TRANSITIONS",
    "VALID_APPROVAL_TRANSITIONS",
    "normalize_status",
    "update_sub_spec_status",
    "update_doc_approval",
    "calculate_summary",
    "derive_workspace_status",
    "create_default_tracker",
    "poll_sub_spec_status",
]

if TYPE_CHECKING:
    from .workspace_tracker import (
        ApprovalDocStatus,
        DocApprovalRecord,
        DocApprovals,
        PollResult,
        SubSpecUpdate,
        TrackerData,
        TrackerSubSpec,
        TrackerSummary,
        WorkspaceStatus,
    )

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"spec_created", "requirements_created", "cancelled"},
    "spec_created": {"approved", "rejected", "cancelled"},
    "rejected": {"spec_created", "cancelled"},
    "requirements_created": {"requirements_approved", "cancelled"},
    "requirements_approved": {"design_created", "cancelled"},
    "design_created": {"design_approved", "cancelled"},
    "design_approved": {"tasks_created", "cancelled"},
    "tasks_created": {"approved", "cancelled"},
    "approved": {"in_progress", "cancelled"},
    "in_progress": {"completed", "blocked", "failed", "cancelled"},
    "blocked": {"in_progress", "cancelled"},
    "failed": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

VALID_APPROVAL_TRANSITIONS: dict[str, set[str]] = {
    "not_requested": {"pending", "approved"},
    "pending": {"approved", "revision_requested", "rejected"},
    "revision_requested": {"pending"},
    "rejected": set(),
    "approved": set(),
}

_STATUS_SUMMARY_KEY_MAP: dict[str, str] = {
    "in_progress": "inProgress",
    "spec_created": "specCreated",
    "requirements_created": "requirementsCreated",
    "requirements_approved": "requirementsApproved",
    "design_created": "designCreated",
    "design_approved": "designApproved",
    "tasks_created": "tasksCreated",
}

_HYPHENATED_COMPAT: dict[str, str] = {
    "in-progress": "in_progress",
    "needs-revision": "needs_revision",
}


def _status_to_summary_key(status: str) -> str:
    return _STATUS_SUMMARY_KEY_MAP.get(status, status)


def normalize_status(status: str) -> str:
    """Normalize legacy hyphenated status names to underscore form."""
    return _HYPHENATED_COMPAT.get(status, status)


def _find_sub_spec(tracker: TrackerData, repo_id: str) -> TrackerSubSpec | None:
    return find_by_key(tracker.get("subSpecs", []), "repoId", repo_id)


def _default_doc_record() -> DocApprovalRecord:
    return {"approvalId": None, "status": "not_requested", "timestamp": None}


def _default_doc_approvals() -> DocApprovals:
    return {doc: _default_doc_record() for doc in DOC_NAMES}


def update_sub_spec_status(tracker: TrackerData, repo_id: str, status: SubSpecUpdate) -> TrackerData:
    """Update one sub-spec entry. Validates status transitions."""
    sub_specs = tracker.setdefault("subSpecs", [])
    entry = _find_sub_spec(tracker, repo_id)

    new_status = normalize_status(status.get("status", "pending"))

    if entry is None:
        entry = {"repoId": repo_id, "status": "pending"}
        sub_specs.append(entry)

    current_status = normalize_status(entry.get("status", "pending"))
    if current_status != new_status:
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: '{current_status}' → '{new_status}'. "
                f"Allowed: {sorted(allowed)}"
            )

    entry.update(status)
    entry["lastChecked"] = sdd_time.ts_now()

    return tracker


def update_doc_approval(
    tracker: TrackerData,
    target: str,
    doc: str,
    approval_id: Optional[str],
    status: ApprovalDocStatus,
    timestamp: Optional[str] = None,
) -> None:
    """Record approval state for a specific document."""
    from .workspace_tracker import is_v2

    if doc not in DOC_NAMES:
        raise ValueError(f"Invalid doc '{doc}'. Must be one of {DOC_NAMES}")

    if target == "coordination":
        if is_v2(tracker):
            raise ValueError(
                "target='coordination' is not supported in schema v2.0.0+. "
                "Use the coordinator's repo ID instead."
            )
        approvals = tracker.setdefault("coordinationApprovals", _default_doc_approvals())
    else:
        entry = _find_sub_spec(tracker, target)
        if entry is None:
            raise ValueError(f"No sub-spec found for repo '{target}'")
        approvals = entry.setdefault("approvals", _default_doc_approvals())

    record = approvals.get(doc)
    if record is None:
        record = _default_doc_record()
        approvals[doc] = record

    current = record.get("status", "not_requested")
    if current != status:
        allowed = VALID_APPROVAL_TRANSITIONS.get(current, set())
        if status not in allowed:
            raise ValueError(
                f"Invalid approval transition for {target}/{doc}: "
                f"'{current}' → '{status}'. Allowed: {sorted(allowed)}"
            )

    record["approvalId"] = approval_id
    record["status"] = status
    if timestamp is not None:
        record["timestamp"] = timestamp


def calculate_summary(tracker: TrackerData) -> TrackerSummary:
    """Recalculate summary block from all subSpecs entries (single pass)."""
    from .workspace_tracker_validation import VALID_STATUSES

    sub_specs = tracker.get("subSpecs", [])
    status_counts: Counter = Counter()
    approved_count = 0
    has_doc_status = False

    for s in sub_specs:
        status_counts[s.get("status", "pending")] += 1
        if s.get("docStatus"):
            has_doc_status = True
        approvals = s.get("approvals", {})
        if approvals and all(
            approvals.get(doc, {}).get("status") == "approved"
            for doc in DOC_NAMES
        ):
            approved_count += 1

    summary: dict = {"totalSubSpecs": len(sub_specs)}
    for status in VALID_STATUSES:
        summary[_status_to_summary_key(status)] = status_counts.get(status, 0)
    summary["approvedSubSpecs"] = approved_count

    if has_doc_status:
        from . import workspace_query
        summary["byPhase"] = {
            doc: workspace_query.phase_progress_summary(tracker, doc)
            for doc in DOC_NAMES
        }

    return summary


def derive_workspace_status(tracker: TrackerData) -> WorkspaceStatus:
    """Compute the top-level workspace status from sub-spec states."""
    sub_specs = tracker.get("subSpecs", [])
    if not sub_specs:
        return "in_progress"

    statuses = [s.get("status", "pending") for s in sub_specs]

    if all(s == "cancelled" for s in statuses):
        return "cancelled"
    if all(s in ("completed", "cancelled") for s in statuses):
        return "completed"
    if any(s == "blocked" for s in statuses):
        return "blocked"
    return "in_progress"


def create_default_tracker(
    feature: str,
    *,
    repos: list[dict] | None = None,
) -> TrackerData:
    """Single source of truth for a blank tracker."""
    now = sdd_time.ts_now()
    tracker: TrackerData = {
        "schemaVersion": "2.0.0",
        "feature": feature,
        "status": "in_progress",
        "createdAt": now,
        "updatedAt": now,
        "subSpecs": [],
        "summary": {},
    }

    if repos is not None:
        for r in repos:
            tracker["subSpecs"].append({
                "repoId": r.get("id", ""),
                "repoName": r.get("name", ""),
                "repoPath": r.get("path", ""),
                "subSpecName": r.get("subSpec", ""),
                "repoType": r.get("repoType", "target"),
                "status": "pending",
            })
    else:
        tracker["coordinationApprovals"] = _default_doc_approvals()

    return tracker


def poll_sub_spec_status(
    sub_specs: list[TrackerSubSpec],
    *,
    paths_module,
    specs_module,
    approvals_module,
) -> list[PollResult]:
    """Poll live spec status from each target repo sub-spec entry."""
    results = []
    for sub in sub_specs:
        repo_path = sub.get("repoPath", "")
        repo_id = sub.get("repoId", "")
        sub_spec_name = sub.get("subSpecName", "")
        if not repo_path:
            results.append({
                "repoId": repo_id,
                "pollStatus": "error",
                "message": "No repo path in tracker entry",
            })
            continue
        try:
            target_root = paths_module.find_workflow_root(repo_path)
        except FileNotFoundError:
            results.append({
                "repoId": repo_id,
                "pollStatus": "not_initialized",
                "message": f"No .spec-workflow/ in {repo_path}",
            })
            continue
        try:
            all_approvals = approvals_module.scan_approvals(
                paths_module.approvals_dir(target_root)
            )
            phase_info = specs_module.detect_spec_phase(
                target_root, sub_spec_name, approvals_list=all_approvals,
            )
            results.append({
                "repoId": repo_id,
                "pollStatus": "ok",
                "phase": phase_info.get("phase"),
                "status": phase_info.get("status"),
                "taskProgress": phase_info.get("taskProgress"),
            })
        except Exception as exc:
            results.append({
                "repoId": repo_id,
                "pollStatus": "error",
                "message": str(exc),
            })
    return results
