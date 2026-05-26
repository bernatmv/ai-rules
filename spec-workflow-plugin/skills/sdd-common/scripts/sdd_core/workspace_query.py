"""Shared filter/query helpers for workspace phase operations.

Leaf module with no internal workspace dependencies — operates on raw
TrackerData dicts.  Used by ``workspace_phase``, ``workspace_approval``,
CLI scripts, and status builders.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

__all__ = [
    "active_repos",
    "filter_by_doc_status",
    "all_active_at_doc_status",
    "repos_needing_work",
    "phase_progress_summary",
    "categorize_repos_by_doc_status",
    "build_workspace_status",
    "WorkspaceCallContext",
    "is_workspace_context",
]


def _match_subspec(target_name: str, sub: dict) -> bool:
    """True when *sub* names *target_name* via ``subSpecName`` or ``repoId``."""
    return target_name in {
        sub.get("subSpecName") or "",
        sub.get("repoId") or "",
    }


@dataclass(frozen=True)
class WorkspaceCallContext:
    """Workspace coordinates for a target that sits inside a workspace.

    ``feature`` is the workspace feature name; ``repo_id`` is the
    sub-spec / target repo declared on the workspace manifest;
    ``workspace_root`` is the absolute path to the coordinator root;
    ``current_phase`` is the phase the workspace tracker reports for
    the target (empty string when the tracker has no value yet).
    """

    feature: str
    repo_id: str
    workspace_root: str
    current_phase: str


def is_workspace_context(
    category: str, target_name: str, project_path: str,
) -> "WorkspaceCallContext | None":
    """Return a :class:`WorkspaceCallContext` when *target_name* sits inside a workspace.

    Two-stage probe:

    1. Parent walk via :func:`paths.find_workspace_tracker_root` —
       satisfies callers running under the coordinator.
    2. Fallback manifest sweep via :func:`paths.find_workspace_for_target` —
       satisfies target-rooted callers whose CWD does not nest under
       the coordinator.

    Returns ``None`` only when neither probe succeeds.
    """
    from . import paths as _paths
    from . import workspace_tracker as _tracker

    if category not in {"spec", "workspace"}:
        return None
    workspace_root = _paths.find_workspace_tracker_root(project_path)
    if workspace_root:
        for feature, tracker, sub in _tracker.iter_workspace_subspecs(workspace_root):
            if _match_subspec(target_name, sub):
                return WorkspaceCallContext(
                    feature=feature,
                    repo_id=sub.get("repoId") or "",
                    workspace_root=str(workspace_root),
                    current_phase=tracker.get("currentPhase") or "",
                )
    swept = _paths.find_workspace_for_target(
        target_name, search_roots=[project_path or "."],
    )
    if swept is None:
        return None
    feature, repo_id, coord_root = swept
    return WorkspaceCallContext(
        feature=feature,
        repo_id=repo_id,
        workspace_root=coord_root,
        current_phase="",
    )

_TERMINAL_STATUSES = frozenset({"cancelled", "failed"})


def active_repos(tracker: dict) -> list[dict]:
    """Repos not cancelled/failed — the working set for phase operations."""
    return [
        s for s in tracker.get("subSpecs", [])
        if s.get("status") not in _TERMINAL_STATUSES
    ]


def filter_by_doc_status(
    tracker: dict, doc: str, status: str | set[str],
) -> list[dict]:
    """Return sub-specs whose ``docStatus.{doc}`` matches *status*."""
    if isinstance(status, str):
        status = {status}
    return [
        s for s in tracker.get("subSpecs", [])
        if s.get("docStatus", {}).get(doc) in status
    ]


def all_active_at_doc_status(
    tracker: dict, doc: str, target_status: str,
) -> bool:
    """True when every active repo has ``docStatus.{doc} == target_status``."""
    active = active_repos(tracker)
    if not active:
        return False
    return all(
        s.get("docStatus", {}).get(doc) == target_status
        for s in active
    )


def repos_needing_work(
    tracker: dict, doc: str,
) -> list[dict]:
    """Repos with ``docStatus.{doc}`` in ``('pending', 'revision_requested')``."""
    return filter_by_doc_status(tracker, doc, {"pending", "revision_requested"})


def phase_progress_summary(
    tracker: dict, doc: str,
) -> dict[str, int]:
    """Count repos per docStatus value for a given doc type.

    Powers the ``summary.byPhase`` calculation.
    """
    counts: Counter = Counter()
    for s in tracker.get("subSpecs", []):
        doc_status = s.get("docStatus", {}).get(doc, "pending")
        counts[doc_status] += 1
    return dict(counts)


def categorize_repos_by_doc_status(
    tracker: dict, phase: str,
) -> dict[str, list[str]]:
    """Categorize active repos by their ``docStatus.{phase}`` value.

    Returns ``{"approved": [...], "skipped": [...], "failed": [...]}``
    where each list contains repo-ID strings.
    """
    result: dict[str, list[str]] = {"approved": [], "skipped": [], "failed": []}
    for s in active_repos(tracker):
        status = s.get("docStatus", {}).get(phase)
        if status in result:
            result[status].append(s.get("repoId", ""))
    return result


def build_workspace_status(
    manifest: dict, tracker: dict, poll_results: list | None = None,
) -> dict:
    """Build a consolidated workspace status dict from manifest + tracker.

    Reusable by ``check-status.py`` and ``phase-status.py``.

    For v2.0.0+ trackers the coordinator is in ``subSpecs[]`` — no
    separate ``coordinator`` / ``coordinationApprovals`` fields are emitted.
    For v1.x trackers the legacy fields are preserved.
    """
    from .workspace_tracker import is_v2
    from .workspace_manifest import get_coordinator

    summary = tracker.get("summary", {})
    data: dict = {
        "feature": tracker.get("feature", manifest.get("feature", "unknown")),
        "status": tracker.get("status", "unknown"),
        "subSpecs": tracker.get("subSpecs", []),
        "summary": summary,
    }

    if is_v2(tracker):
        coord = get_coordinator(manifest)
        if coord:
            data["coordinator"] = {
                "id": coord.get("id", "unknown"),
                "role": coord.get("role", "N/A"),
            }
    else:
        coordinator_legacy = manifest.get("coordinator", {})
        data["coordinator"] = {
            "id": coordinator_legacy.get("id", "unknown"),
            "role": coordinator_legacy.get("role", "N/A"),
        }
        data["coordinationApprovals"] = tracker.get("coordinationApprovals", {})

    current_phase = tracker.get("currentPhase")
    if current_phase is not None:
        data["currentPhase"] = current_phase

    phase_gates = tracker.get("phaseGates")
    if phase_gates is not None:
        data["phaseGates"] = phase_gates

    if poll_results:
        data["pollResults"] = poll_results

    return data
