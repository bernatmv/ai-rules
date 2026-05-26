"""Transient review-pipeline state — co-location + cleanup facade.

Co-locates the three review-pipeline runtime artifacts under
``<doc_dir>/.sdd-state/`` where ``<doc_dir>`` resolves through one of
the canonical category buckets (``specs`` / ``steering`` / ``discovery``
/ ``workspace``; see :data:`sdd_core.paths._CATEGORY_BUCKETS`):

* ``gate-session.json``              — current gate position, cache keys,
                                        fix-loop counters (atomic JSON).
* ``reference-ledger.jsonl``         — append-only audit trail of
                                        mandatory pre-flight reads/runs.
* ``review-assessment-staging.json`` — staged tier-2 scores and cross-
                                        validation results awaiting the
                                        fold into ``review-quality.json``.

Each owning module (``reference_ledger``,
``review_quality.gate_session.io``, ``review.pipeline_phases.resolvers``)
keeps its own formatter and writer and resolves the containing directory
through :func:`state_dir`. The approval flow depends only on the
:func:`cleanup_on_approval` facade. Helpers delegate I/O to the owning
modules which honour ``sdd_core.output._dry_run_active``.

``.sdd-state/`` is the single contract; orphan files outside this
directory are ignored and fresh sessions start fresh.
"""
from __future__ import annotations

import enum
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from sdd_core.paths import (
    STATE_DIR_NAME as _PATHS_STATE_DIR_NAME,
    doc_dir_path,
    workflow_state_path,
)

__all__ = [
    "STATE_DIR_NAME",
    "GATE_SESSION_FILENAME",
    "LEDGER_FILENAME",
    "STAGING_FILENAME",
    "STAGING_FILENAME_PREFIX",
    "STAGING_FILENAME_SUFFIX",
    "staging_filename",
    "iter_staging_filenames",
    "PRELOAD_STATE_FILENAME",
    "CURRENT_TARGET_FILENAME",
    "CleanupReport",
    "CleanupMode",
    "APPROVAL_OUTCOMES",
    "state_dir",
    "state_path",
    "ensure_state_dir",
    "cleanup_on_approval",
    "preload_tool_search_command",
    "preload_advisory_detail",
    "record_deferred_tool_preload",
    "load_deferred_tool_preload",
    "get_deferred_tool_preload",
    "read_current_target",
    "write_current_target",
    "clear_current_target",
]

# Canonical outcome vocabulary for approval transitions. Mirrors the
# values produced by ``sdd_core.approvals.STATUS_TRANSITIONS`` so the
# cleanup facade accepts exactly what the approval pipeline emits.
APPROVAL_OUTCOMES = ("approved", "rejected", "needs_revision")

# Approval categories this facade knows how to clean up. Other
# categories (ad-hoc reviews, custom) are accepted but short-circuit
# with mode=``unsupported`` so callers still get a stable envelope.
SUPPORTED_CATEGORIES = ("steering", "spec", "discovery", "workspace")

# Re-exported for backwards imports (``from sdd_core.transient_state
# import STATE_DIR_NAME``). The canonical definition lives in
# :mod:`sdd_core.paths` so cross-category state files (``harness.json``,
# ``deferred-tool-preload.json``) and per-doc-target state (gate session,
# ledger, staging) share one authority.
STATE_DIR_NAME = _PATHS_STATE_DIR_NAME

# Canonical filenames inside ``.sdd-state/``. No leading dot — the
# containing directory is already hidden, so nesting another dot would
# be noise without benefit.
GATE_SESSION_FILENAME = "gate-session.json"
LEDGER_FILENAME = "reference-ledger.jsonl"
# Legacy (gate-id-less) staging filename. Per-gate staging files use
# the ``review-assessment-staging-<gate_id>.json`` shape derived from
# :func:`staging_filename`. Readers fall back to the legacy name when a
# per-gate file is absent so a transition cycle does not lose staged
# scores; writers always produce the per-gate shape when a gate-id is
# available.
STAGING_FILENAME = "review-assessment-staging.json"
STAGING_FILENAME_PREFIX = "review-assessment-staging-"
STAGING_FILENAME_SUFFIX = ".json"


def staging_filename(gate_id: str = "") -> str:
    """Return the staging JSON filename for *gate_id*.

    With a non-empty ``gate_id``: ``review-assessment-staging-<gate_id>.json``
    so multiple gates under one doc target can stage independently
    without colliding. With an empty ``gate_id``: the legacy
    :data:`STAGING_FILENAME` shape — kept so call sites that have no
    gate context (entry-style phases, ad-hoc tooling) keep working.
    """
    if gate_id:
        return f"{STAGING_FILENAME_PREFIX}{gate_id}{STAGING_FILENAME_SUFFIX}"
    return STAGING_FILENAME


def iter_staging_filenames(state_dir_path: str) -> list[str]:
    """Return every staging-shaped filename present under *state_dir_path*.

    Includes both the legacy :data:`STAGING_FILENAME` and any per-gate
    ``review-assessment-staging-<gate_id>.json`` siblings. Used by the
    approval-completion cleanup so a workflow that produced a per-gate
    file does not leak the file past approval. Missing directory →
    empty list (callers treat staging cleanup as best-effort).
    """
    try:
        entries = os.listdir(state_dir_path)
    except (FileNotFoundError, NotADirectoryError, OSError):
        return []
    matched: list[str] = []
    for entry in entries:
        if entry == STAGING_FILENAME:
            matched.append(entry)
        elif (
            entry.startswith(STAGING_FILENAME_PREFIX)
            and entry.endswith(STAGING_FILENAME_SUFFIX)
        ):
            matched.append(entry)
    return matched
# Per-project record of the most recent deferred-tool preload so the
# health facade's advisory quiets after the first preload instead of
# firing on every tick.
PRELOAD_STATE_FILENAME = "deferred-tool-preload.json"

# Per-project record of the workflow's currently-active target.
# Written by phase entry points; read by ``sdd_core.context``'s
# session resolver. Lives at ``<workflow>/.sdd-state/`` so
# cleanup_on_approval clears it on final approval.
CURRENT_TARGET_FILENAME = "current-target.json"


def state_dir(
    category: str, target_name: str, project_path: str = "",
) -> str:
    """Return the ``.sdd-state/`` directory path for a doc target."""
    return os.path.join(
        doc_dir_path(category, target_name, project_path),
        STATE_DIR_NAME,
    )


def state_path(
    category: str,
    target_name: str,
    filename: str,
    project_path: str = "",
) -> str:
    """Return the canonical path of a transient-state file."""
    return os.path.join(
        state_dir(category, target_name, project_path), filename,
    )


def ensure_state_dir(
    category: str, target_name: str, project_path: str = "",
) -> str:
    """Create ``.sdd-state/`` on demand and return the path.

    Best-effort (mirrors ``reference_ledger.append`` semantics): a
    missing parent doc-directory silently no-ops and returns the path
    anyway, because writers treat these directories as optional.
    """
    path = state_dir(category, target_name, project_path)
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except OSError:
        # Writers already tolerate unwritable state dirs (see e.g.
        # ``reference_ledger.append`` catching OSError on parent.mkdir).
        pass
    return path


# ---------------------------------------------------------------------------
# Approval-completion cleanup
#
# The approval pipeline owns the lifecycle boundary for transient
# review state. ``cleanup_on_approval`` is the single authority hooked
# into ``approval/update-status.py``. The policy matrix is expressed
# declaratively so reviewers can diff the table in isolation without
# reading the delete helpers.
# ---------------------------------------------------------------------------


# Observable mode values surfaced in ``CleanupReport.mode`` so agents
# can distinguish "nothing to clean" from "dry-run suppressed I/O" or
# "approval category outside the cleanup policy".
class CleanupMode(str, enum.Enum):
    APPLIED = "applied"
    DRY_RUN = "dry_run"
    UNSUPPORTED = "unsupported"

    def __str__(self) -> str:  # str-equality keeps existing comparisons working
        return self.value


@dataclass
class CleanupReport:
    """Structured audit of what a cleanup pass did.

    Three lists so the approval-success envelope can show — at a
    glance — which files went away, which were archived (ledger audit
    trail), and which were intentionally preserved (fix-loop in
    flight). ``mode`` distinguishes "applied" from "dry_run" /
    "unsupported" so an empty payload is never ambiguous.
    """

    deleted: list[str] = field(default_factory=list)
    archived: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    mode: str = CleanupMode.APPLIED

    def to_dict(self) -> dict:
        mode = self.mode
        if isinstance(mode, CleanupMode):
            mode = mode.value
        return {
            "deleted": list(self.deleted),
            "archived": list(self.archived),
            "kept": list(self.kept),
            "mode": mode,
        }


# Policy matrix: per-outcome action for each managed file.
#   "delete"  — unlink the canonical path.
#   "archive" — move the file into ``.sdd-state/.archive/`` (ledger only).
#   "keep"    — leave the file untouched; add to ``kept`` for auditing.
#
# The table is intentionally declarative so reviewers can audit the
# lifecycle policy without tracing through conditional code.
_CLEANUP_POLICY: dict[str, dict[str, str]] = {
    "approved": {
        GATE_SESSION_FILENAME: "delete",
        STAGING_FILENAME: "delete",
        LEDGER_FILENAME: "archive",
    },
    "rejected": {
        GATE_SESSION_FILENAME: "delete",
        STAGING_FILENAME: "delete",
        LEDGER_FILENAME: "keep",
    },
    "needs_revision": {
        GATE_SESSION_FILENAME: "keep",
        STAGING_FILENAME: "delete",
        LEDGER_FILENAME: "keep",
    },
}


def _unlink_if_present(path: str) -> list[str]:
    """Unlink ``path`` if it exists, returning ``[path]`` on success.

    Missing or unremovable files produce ``[]`` so the caller can
    distinguish "nothing to clean" from "cleaned N files". Best-effort
    — transient-state cleanup never blocks approval on filesystem
    errors.
    """
    try:
        os.unlink(path)
    except FileNotFoundError:
        return []
    except OSError:
        return []
    return [path]


def cleanup_on_approval(
    *,
    category: str,
    target_name: str,
    outcome: str,
    project_path: str = "",
) -> CleanupReport:
    """Apply the approval-completion cleanup policy for a review target.

    Parameters
    ----------
    outcome : str
        One of :data:`APPROVAL_OUTCOMES`. Any other value raises
        ``ValueError`` — callers must not invent new approval states
        without first extending the policy matrix above.

    Honours the pipeline dry-run flag: inside a dry run the facade is
    a pure read and returns an empty ``CleanupReport`` so subprocesses
    cannot leak state.

    Returns a :class:`CleanupReport` that the approval script embeds
    in the success envelope (``cleanup`` key) so agents can observe
    exactly what was cleaned. This closes the feedback loop called out
    in Anthropic's "Workflows and feedback loops" guidance.
    """
    if outcome not in APPROVAL_OUTCOMES:
        raise ValueError(
            f"unknown approval outcome {outcome!r}; expected one of "
            f"{APPROVAL_OUTCOMES!r}"
        )

    if category not in SUPPORTED_CATEGORIES:
        # Stable envelope for ad-hoc / custom categories that do not
        # participate in the review-pipeline cleanup policy.
        return CleanupReport(mode=CleanupMode.UNSUPPORTED)

    # Lazy import avoids a circular dependency — ``output`` imports
    # ``sdd_core`` transitively for envelope helpers.
    from sdd_core.output import _dry_run_active

    if _dry_run_active():
        # Dry-run contract: never touch disk. ``mode`` distinguishes
        # the empty payload from an "applied" no-op.
        return CleanupReport(mode=CleanupMode.DRY_RUN)

    policy = _CLEANUP_POLICY[outcome]
    report = CleanupReport()
    state_dir_path = state_dir(category, target_name, project_path)

    for filename, action in policy.items():
        canonical = state_path(
            category, target_name, filename, project_path,
        )
        if action == "delete":
            # The staging policy entry covers both the legacy filename
            # and any per-gate ``review-assessment-staging-<gate_id>.json``
            # siblings — a workflow that produced the per-gate shape
            # must not leak that file past the approval boundary.
            if filename == STAGING_FILENAME:
                targets = [
                    os.path.join(state_dir_path, name)
                    for name in iter_staging_filenames(state_dir_path)
                ] or [canonical]
            else:
                targets = [canonical]
            any_removed = False
            for target in targets:
                removed = _unlink_if_present(target)
                if removed:
                    report.deleted.extend(removed)
                    any_removed = True
            if not any_removed:
                report.kept.append(canonical)
        elif action == "archive":
            # Only the ledger has archival semantics today. Dispatch
            # by filename so new managed files can slot in without
            # extending this branch.
            if filename == LEDGER_FILENAME:
                # Lazy import: ``reference_ledger`` imports this
                # module, so the reverse dependency must be deferred.
                from sdd_core import reference_ledger
                archived = reference_ledger.archive_to(
                    category, target_name, project_path=project_path,
                )
                if archived:
                    report.archived.append(archived)
                else:
                    report.kept.append(canonical)
            else:  # pragma: no cover — guard against future policy drift
                raise NotImplementedError(
                    f"archive action not implemented for {filename!r}"
                )
        elif action == "keep":
            report.kept.append(canonical)
        else:  # pragma: no cover — guard against future policy drift
            raise ValueError(
                f"unknown cleanup action {action!r} for {filename!r}"
            )

    # ``current-target.json`` is workspace-scoped, not per-doc-target —
    # final approval (only) clears it so the next workflow boots clean.
    #
    # Workspace-scoped state explicitly excluded from approval cleanup:
    # ``preflight.json`` and ``session-*.json`` survive approvals
    # because pre-flight advisories outlive any single spec's approval
    # and the active harness session must persist across them.
    if outcome == "approved":
        current_target = _current_target_path(project_path)
        removed = _unlink_if_present(current_target)
        if removed:
            report.deleted.extend(removed)

    return report


# ---------------------------------------------------------------------------
# Deferred-tool preload record.
#
# The file sits under ``<project>/.spec-workflow/.sdd-state/`` alongside
# ``harness.json`` (cross-category, one-per-checkout) so it survives
# every category's gate-session cleanup.
# ---------------------------------------------------------------------------


def _preload_state_path(project_path: str = "") -> str:
    return workflow_state_path(PRELOAD_STATE_FILENAME, project_path)


def preload_tool_search_command(tools: Iterable[str]) -> str:
    """Return the ``ToolSearch`` command that preloads *tools*.

    Single source of truth so ``util/preflight-tools.py`` and the
    ``deferred_tools_preload`` health check surface a literal-identical
    ``next_action_command`` to the agent.
    """
    names = sorted(set(tools))
    joined = ",".join(names)
    return f'ToolSearch query="select:{joined}" max_results={len(names)}'


def preload_advisory_detail(tools: Iterable[str]) -> str:
    """Return the human-readable advisory detail for the preload."""
    names = sorted(set(tools))
    return (
        f"Preload {len(names)} deferred tool schema(s) "
        f"({', '.join(names)}) via ToolSearch before proceeding"
    )


def record_deferred_tool_preload(
    project_path: str, adapter_name: str, tools: Iterable[str],
) -> None:
    """Record that the agent has preloaded the given deferred tools.

    Idempotent: the file is overwritten on every call. Routes through
    :func:`sdd_core.output.atomic_write_json` so JSON state files share
    one durable-write primitive (unique temp file + ``fsync`` +
    rename) instead of risking a partially-flushed payload on crash.
    Best-effort I/O — a read-only checkout silently no-ops.
    """
    # Lazy import: ``output`` pulls in ``sdd_core`` transitively for
    # envelope helpers; deferring the import here mirrors the pattern
    # used by :func:`cleanup_on_approval` above.
    from sdd_core.output import atomic_write_json

    path = _preload_state_path(project_path)
    try:
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
        data = {"harness": adapter_name, "tools": sorted(set(tools))}
        atomic_write_json(path, data)
    except OSError:
        pass


def get_deferred_tool_preload(
    project_path: str, adapter_name: str,
) -> set[str]:
    """Return the set of tools recorded as preloaded.

    Empty set when no record exists, the file is unreadable, or the
    recorded harness does not match *adapter_name*. Single I/O reader
    used by both :func:`load_deferred_tool_preload` (the bool view) and
    the per-tool advisory builder in
    ``workspace_health_checks.check_deferred_tools_preload`` —
    DRY-factored so future readers share one parser.
    """
    path = _preload_state_path(project_path)
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, dict):
        return set()
    if data.get("harness") != adapter_name:
        return set()
    recorded = data.get("tools") or []
    if not isinstance(recorded, list):
        return set()
    return set(recorded)


def load_deferred_tool_preload(
    project_path: str, adapter_name: str, tools: Iterable[str],
) -> bool:
    """Backwards-compat boolean view of :func:`get_deferred_tool_preload`.

    True iff every tool in *tools* is present in the recorded set.
    """
    return set(tools).issubset(
        get_deferred_tool_preload(project_path, adapter_name)
    )


# ---------------------------------------------------------------------------
# Workflow current-target session.
#
# The record sits at the workflow root so a single resolver chain
# (sdd_core.context) can read it across categories without knowing
# the target up front. Atomic writes mirror the gate-session.json
# contract. Lifecycle: cleanup_on_approval (final approval) clears
# the record; explicit ``--reset`` callers can also call
# ``clear_current_target``.
# ---------------------------------------------------------------------------


def _current_target_path(project_path: str = "") -> str:
    return workflow_state_path(CURRENT_TARGET_FILENAME, project_path)


def read_current_target(project_path: str = "") -> dict | None:
    """Return the recorded current-target dict, or ``None`` when absent.

    Schema: ``{"target": str, "phase": str | None, "repo_id": str | None,
    "category": str | None, "updated_at": str | None}``. Missing /
    malformed records produce ``None`` so callers always see a
    well-formed shape or nothing.
    """
    path = _current_target_path(project_path)
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    target = data.get("target")
    if not isinstance(target, str) or not target:
        return None
    return {
        "target": target,
        "phase": data.get("phase") if isinstance(data.get("phase"), str) else None,
        "repo_id": (
            data.get("repo_id") if isinstance(data.get("repo_id"), str) else None
        ),
        "category": (
            data.get("category") if isinstance(data.get("category"), str) else None
        ),
        "updated_at": (
            data.get("updated_at")
            if isinstance(data.get("updated_at"), str)
            else None
        ),
    }


def write_current_target(
    target: str,
    *,
    phase: str | None = None,
    repo_id: str | None = None,
    category: str | None = None,
    project_path: str = "",
    updated_at: str | None = None,
) -> None:
    """Persist the workflow's current target under ``.sdd-state/``.

    Best-effort I/O — read-only checkouts silently no-op. Honours the
    pipeline dry-run gate via :func:`sdd_core.output.atomic_write_json`.
    """
    if not isinstance(target, str) or not target:
        raise ValueError("target must be a non-empty string")

    # Lazy import: ``output`` pulls in ``sdd_core`` transitively for
    # envelope helpers; deferring here mirrors :func:`cleanup_on_approval`.
    from sdd_core.output import atomic_write_json

    path = _current_target_path(project_path)
    record: dict = {"target": target}
    if phase:
        record["phase"] = phase
    if repo_id:
        record["repo_id"] = repo_id
    if category:
        record["category"] = category
    if updated_at:
        record["updated_at"] = updated_at
    try:
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, record)
    except OSError:
        pass


def clear_current_target(project_path: str = "") -> bool:
    """Remove the current-target record. Returns ``True`` when a file was deleted."""
    path = _current_target_path(project_path)
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
