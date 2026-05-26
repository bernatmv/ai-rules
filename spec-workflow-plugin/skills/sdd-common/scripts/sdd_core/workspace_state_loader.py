"""Resolve ``.sdd-state/`` directories under the two-tier layout.

The legacy layout placed every state file under
``<repo>/.spec-workflow/.sdd-state/`` regardless of whether the file
was workspace-wide (``harness.json``, ``reference-acks.json``) or
per-spec (``gate-session.json``, ``reference-ledger.jsonl``,
``review-assessment-staging.json``). The two-tier layout splits these:

  - **per-spec**   — ``<repo>/.spec-workflow/specs/<spec>/.sdd-state/``
  - **workspace**  — ``<coordinator>/.spec-workflow/workspace/<feature>/.sdd-state/``
  - **standalone** — ``<repo>/.spec-workflow/standalone/<spec>/.sdd-state/``
    (fallback when a per-spec file lacks a matching workspace context)

This module owns the policy that maps ``filename -> purpose`` so
adding a new persisted file is one row in :data:`_FILENAME_PURPOSES`
rather than touching every consumer.

Why a new module instead of edits to ``paths.py`` /
``transient_state.py``: those two modules already own filesystem-shape
paths and per-doc-target state. Workspace/spec/standalone resolution
is a third concern (SRP). The new loader **delegates to**
:func:`sdd_core.paths.spec_dir`, :func:`sdd_core.paths.workspace_dir`,
and :data:`sdd_core.paths.WORKFLOW_DIR` — directory shapes stay owned
by ``paths.py``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from . import paths as _paths

__all__ = [
    "Purpose",
    "resolve_state_dir",
    "state_path",
    "purpose_for_filename",
    "PURPOSE_PER_SPEC",
    "PURPOSE_WORKSPACE",
    "PURPOSE_STANDALONE",
    "PURPOSE_AUTO",
]


# State-purpose vocabulary — single source of truth for the
# ``Purpose`` literal. Adding a new tier means one new constant and
# one new branch in :func:`resolve_state_dir`.
PURPOSE_PER_SPEC = "per-spec"
PURPOSE_WORKSPACE = "workspace"
PURPOSE_STANDALONE = "standalone"
PURPOSE_AUTO = "auto"

Purpose = Literal["per-spec", "workspace", "standalone", "auto"]

# ``.sdd-state/`` is the canonical leaf directory under every tier.
# Reuses the literal already owned by ``paths.STATE_DIR_NAME`` so a
# rename lands one place.
_STATE_DIR_NAME = _paths.STATE_DIR_NAME


# Single source of truth — ``filename -> purpose``. Adding a new
# persisted file is one row; consumers never duplicate the rule.
# ``per-spec`` files live with the spec they describe; ``workspace``
# files are cross-repo identity / ack ledgers.
_FILENAME_PURPOSES: dict[str, Purpose] = {
    # Cross-cutting / workspace-wide identity & ack ledgers.
    "harness.json": PURPOSE_WORKSPACE,
    "reference-acks.json": PURPOSE_WORKSPACE,
    "deferred-tool-preload.json": PURPOSE_WORKSPACE,
    # Per-spec gate / staging / audit state.
    "gate-session.json": PURPOSE_PER_SPEC,
    "reference-ledger.jsonl": PURPOSE_PER_SPEC,
    "review-assessment-staging.json": PURPOSE_PER_SPEC,
}


def purpose_for_filename(filename: str, default: Purpose = PURPOSE_AUTO) -> Purpose:
    """Return the registered :data:`Purpose` for *filename* or *default*.

    Filenames with a path component (e.g. ``detect-doc-state/<…>``)
    return *default*: per-doc-target sub-trees route through the
    ``auto`` heuristic so a ``spec_name`` selection still wins when
    one is supplied.
    """
    base = (filename or "").split("/", 1)[0]
    return _FILENAME_PURPOSES.get(base, default)


def _coordinator_root(project_path: str) -> Path:
    """Resolve the workflow root for *project_path* with a soft fallback.

    Mirrors :func:`paths.workflow_state_path` semantics — first-run
    callers without a discovered workflow root still get a usable
    write target (the caller's resolve directory) instead of an
    exception.
    """
    try:
        return _paths.find_workflow_root(project_path or ".")
    except FileNotFoundError:
        return Path(project_path or ".").resolve()


def resolve_state_dir(
    *,
    project_path: str = "",
    feature: str = "",
    spec_name: str = "",
    purpose: Purpose = PURPOSE_AUTO,
) -> Path:
    """Resolve the ``.sdd-state`` directory for a (project, feature, spec) triple.

    Resolution ladder:

    1. ``per-spec``   ⇒ ``<project>/.spec-workflow/specs/<spec_name>/.sdd-state/``
    2. ``workspace``  ⇒ ``<coordinator>/.spec-workflow/workspace/<feature>/.sdd-state/``
    3. ``standalone`` ⇒ ``<project>/.spec-workflow/standalone/<spec_name>/.sdd-state/``

    ``purpose='auto'`` picks step 1 when both ``spec_name`` and
    ``feature`` are passed (gate-session, ledger live with the spec),
    step 2 when only ``feature`` is passed (harness, reference-acks
    live with the workspace), and step 3 when neither workspace nor
    spec context is unambiguous.
    """
    root = _coordinator_root(project_path)

    resolved = purpose
    if resolved == PURPOSE_AUTO:
        if spec_name:
            resolved = PURPOSE_PER_SPEC
        elif feature:
            resolved = PURPOSE_WORKSPACE
        else:
            resolved = PURPOSE_STANDALONE

    if resolved == PURPOSE_PER_SPEC and spec_name:
        return _paths.spec_dir(root, spec_name) / _STATE_DIR_NAME
    if resolved == PURPOSE_WORKSPACE:
        return _paths.workspace_dir(root, feature) / _STATE_DIR_NAME
    if resolved == PURPOSE_STANDALONE and spec_name:
        return (
            root / _paths.WORKFLOW_DIR / _paths.STANDALONE_DIR_NAME
            / spec_name / _STATE_DIR_NAME
        )
    # Fallback — caller asked for per-spec / standalone but did not
    # supply a spec_name. Drop into the workspace tier when a feature
    # is known; otherwise return the legacy workflow-level state dir
    # so the caller never sees a missing-arg crash on a soft path.
    if feature:
        return _paths.workspace_dir(root, feature) / _STATE_DIR_NAME
    return root / _paths.WORKFLOW_DIR / _STATE_DIR_NAME


def state_path(
    filename: str,
    *,
    project_path: str = "",
    feature: str = "",
    spec_name: str = "",
    purpose: Purpose = PURPOSE_AUTO,
) -> Path:
    """Return the absolute path of *filename* under its resolved state dir.

    Mirrors :func:`transient_state.state_path`'s API so existing
    callers can drop-in. ``purpose='auto'`` consults
    :func:`purpose_for_filename` first; callers that need to override
    the registered policy pass an explicit *purpose*.
    """
    if purpose == PURPOSE_AUTO:
        purpose = purpose_for_filename(filename, default=PURPOSE_AUTO)
    return resolve_state_dir(
        project_path=project_path, feature=feature, spec_name=spec_name,
        purpose=purpose,
    ) / filename
