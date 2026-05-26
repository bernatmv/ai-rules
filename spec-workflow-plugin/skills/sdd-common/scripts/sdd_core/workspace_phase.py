"""Phase lifecycle management for workspace batch-by-document-type flow.

Owns phase transitions, doc-status state machine, and phase-gate recording.
Does not perform I/O — the caller persists via ``workspace_tracker``.
"""
from __future__ import annotations

from . import workspace_query as _query

__all__ = [
    "DOC_PHASES",
    "PHASE_ORDER",
    "PHASE_COMPLETE",
    "DOC_STATUS_TRANSITIONS",
    "VALID_DOC_STATUSES",
    "PHASE_STATUS_MAP",
    "get_current_phase",
    "set_current_phase",
    "advance_phase",
    "advance_with_gate",
    "is_phase_complete",
    "update_doc_status",
    "record_phase_gate",
    "repos_eligible_for_phase",
    "init_doc_status",
    "record_phase_history",
]

# Identical to specs.DOC_NAMES today; kept separate because phases
# could diverge from doc names if non-phase documents are added.
DOC_PHASES = ("requirements", "design", "tasks")

# Terminal phase marker — the value ``currentPhase`` carries once
# the last entry in :data:`PHASE_ORDER` has advanced. Single owner
# (Ousterhout's law / no voodoo constants) so renames or sentinel
# changes flow through one symbol.
PHASE_COMPLETE = "complete"

PHASE_ORDER: dict[str, str | None] = {
    "requirements": "design",
    "design": "tasks",
    "tasks": None,
}

DOC_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending":            {"created", "skipped"},
    "created":            {"validated", "failed"},
    "validated":          {"reviewed", "revision_requested"},
    "reviewed":           {"approved", "revision_requested"},
    "approved":           set(),
    "skipped":            set(),
    "failed":             {"pending"},
    "revision_requested": {"created"},
}

VALID_DOC_STATUSES: frozenset[str] = frozenset(DOC_STATUS_TRANSITIONS.keys())

PHASE_STATUS_MAP: dict[str, str] = {
    "requirements": "requirements_created",
    "design": "design_created",
    "tasks": "tasks_created",
    "implementation": "in_progress",
    "completed": "completed",
}

_VALID_PHASES = frozenset((*DOC_PHASES, PHASE_COMPLETE))


def _default_doc_status() -> dict[str, str]:
    return {doc: "pending" for doc in DOC_PHASES}


def init_doc_status(tracker: dict) -> None:
    """Ensure every sub-spec has a ``docStatus`` field with defaults."""
    for sub in tracker.get("subSpecs", []):
        sub.setdefault("docStatus", _default_doc_status())


def get_current_phase(tracker: dict) -> str | None:
    """Read ``currentPhase``, falling back to inference for v1.1.0 trackers."""
    phase = tracker.get("currentPhase")
    if phase is not None:
        return phase
    sub_specs = tracker.get("subSpecs", [])
    if not sub_specs:
        return None
    for sub in sub_specs:
        ds = sub.get("docStatus", {})
        if ds.get("tasks") in ("approved", "skipped"):
            continue
        if ds.get("design") in ("approved", "skipped"):
            return "tasks"
        if ds.get("requirements") in ("approved", "skipped"):
            return "design"
        return "requirements"
    return PHASE_COMPLETE


def set_current_phase(tracker: dict, phase: str) -> None:
    """Set ``currentPhase`` with validation.

    Raises
    ------
    ValueError
        When *phase* is not in :data:`_VALID_PHASES` (the
        :data:`DOC_PHASES` tuple plus :data:`PHASE_COMPLETE`).
    """
    if phase not in _VALID_PHASES:
        raise ValueError(
            f"Invalid phase '{phase}'. Must be one of {sorted(_VALID_PHASES)}"
        )
    tracker["currentPhase"] = phase


def advance_phase(tracker: dict) -> str:
    """Validate current phase is complete, then advance to next.

    Returns the new phase string.  Raises ``ValueError`` if preconditions
    are not met.
    """
    current = get_current_phase(tracker)
    if current is None:
        raise ValueError("Cannot advance: currentPhase is not set")
    if current == PHASE_COMPLETE:
        raise ValueError("Cannot advance: workspace is already complete")
    if current not in PHASE_ORDER:
        raise ValueError(f"Cannot advance: unknown phase '{current}'")

    if not is_phase_complete(tracker, current):
        raise ValueError(
            f"Cannot advance from '{current}': "
            f"not all active repos are approved/skipped"
        )

    next_phase = PHASE_ORDER[current]
    new_phase = next_phase if next_phase is not None else PHASE_COMPLETE
    set_current_phase(tracker, new_phase)
    return new_phase


def record_phase_history(
    tracker: dict,
    phase: str,
    *,
    advanced_by: "str | None" = None,
    approval_id: "str | None" = None,
) -> dict:
    """Append a ``phaseHistory`` entry for the just-completed *phase*.

    Returns the entry written. Each entry's ``entered_at`` defaults to
    the prior entry's ``exited_at`` (or the tracker ``createdAt`` for
    the first entry), so the timeline reconstructs without needing a
    pre-write hook on the inverse transition.
    """
    from . import time as sdd_time

    history = tracker.setdefault("phaseHistory", [])
    now = sdd_time.ts_now()
    if history:
        entered_at = history[-1].get("exited_at") or now
    else:
        entered_at = tracker.get("createdAt") or now
    entry = {
        "phase": phase,
        "entered_at": entered_at,
        "exited_at": now,
        "approval_id": approval_id,
        "advanced_by": advanced_by,
    }
    history.append(entry)
    return entry


def advance_with_gate(
    tracker: dict,
    phase: str,
    *,
    categories: "dict[str, list[str]] | None" = None,
    advanced_by: "str | None" = None,
    approval_id: "str | None" = None,
) -> "str | None":
    """Record phase gate + advance ``currentPhase`` atomically.

    Composes :func:`is_phase_complete`, :func:`record_phase_gate`, and
    :func:`set_current_phase` in the order ``workspace/advance-phase.py``
    has used inline since its inception. Returns the new phase string
    when advancement happens, or ``None`` when the phase is not yet
    complete.

    *categories* is optional — when omitted it is computed from the
    tracker via :func:`workspace_query.categorize_repos_by_doc_status`.
    Callers that already have the categorisation pass it in to avoid
    walking the sub-spec list twice (e.g. ``apply_phase_approval``
    which has just produced its own per-repo result list).

    Raises
    ------
    ValueError
        Propagated from :func:`set_current_phase` when the resolved
        next-phase value is unknown.
    """
    if not is_phase_complete(tracker, phase):
        return None
    if categories is None:
        categories = _query.categorize_repos_by_doc_status(tracker, phase)
    record_phase_gate(
        tracker,
        phase,
        categories.get("approved", []),
        categories.get("skipped", []),
        categories.get("failed", []),
    )
    record_phase_history(
        tracker, phase,
        advanced_by=advanced_by, approval_id=approval_id,
    )
    next_phase = PHASE_ORDER.get(phase)
    new_phase = next_phase if next_phase is not None else PHASE_COMPLETE
    set_current_phase(tracker, new_phase)
    return new_phase


def is_phase_complete(tracker: dict, phase: str) -> bool:
    """True when all active repos have ``docStatus.{phase}`` in
    ``('approved', 'skipped')``."""
    active = _query.active_repos(tracker)
    if not active:
        return True
    return all(
        s.get("docStatus", {}).get(phase) in ("approved", "skipped")
        for s in active
    )


def update_doc_status(
    tracker: dict, repo_id: str, doc: str, new_status: str,
) -> None:
    """Transition ``docStatus.{doc}`` for one repo.  Validates transition."""
    if doc not in DOC_PHASES:
        raise ValueError(
            f"Invalid doc '{doc}'. Must be one of {DOC_PHASES}"
        )
    if new_status not in VALID_DOC_STATUSES:
        raise ValueError(
            f"Invalid doc status '{new_status}'. "
            f"Must be one of {sorted(VALID_DOC_STATUSES)}"
        )

    sub_specs = tracker.get("subSpecs", [])
    entry = next(
        (s for s in sub_specs if s.get("repoId") == repo_id), None,
    )
    if entry is None:
        raise ValueError(f"No sub-spec found for repo '{repo_id}'")

    doc_status = entry.setdefault("docStatus", _default_doc_status())

    current = doc_status.get(doc, "pending")
    if current != new_status:
        allowed = DOC_STATUS_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid docStatus transition for {repo_id}/{doc}: "
                f"'{current}' → '{new_status}'. Allowed: {sorted(allowed)}"
            )

    doc_status[doc] = new_status


def record_phase_gate(
    tracker: dict,
    phase: str,
    repos_approved: list[str],
    repos_skipped: list[str],
    repos_failed: list[str],
) -> None:
    """Write the ``phaseGates.{phase}`` checkpoint."""
    from . import time as sdd_time

    gates = tracker.setdefault("phaseGates", {
        doc: None for doc in DOC_PHASES
    })
    now = sdd_time.ts_now()
    gates[phase] = {
        "reviewedAt": now,
        "approvedAt": now,
        "reposApproved": repos_approved,
        "reposSkipped": repos_skipped,
        "reposFailed": repos_failed,
    }


def repos_eligible_for_phase(
    tracker: dict, phase: str, manifest: dict,
) -> list[dict]:
    """Active repos not in manifest ``skipPhases`` for this phase."""
    active = _query.active_repos(tracker)
    repos_by_id = {r["id"]: r for r in manifest.get("repos", [])}

    eligible = []
    for s in active:
        repo_id = s.get("repoId", "")
        repo_info = repos_by_id.get(repo_id, {})
        skip_phases = repo_info.get("skipPhases", [])
        if phase not in skip_phases:
            eligible.append(s)
    return eligible
