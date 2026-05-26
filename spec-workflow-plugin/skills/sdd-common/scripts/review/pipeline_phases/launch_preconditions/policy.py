"""Severity decisions + applicability rules for launch preconditions."""
from __future__ import annotations

from typing import Iterable

from sdd_core import reference_ledger
from review_quality.constants import SCOPE_PER_DOCUMENT

from .types import (
    AdvisoryEchoPrecondition,
    AnyPrecondition,
    PostChangeReviewPrecondition,
    Precondition,
    ReferenceReadPrecondition,
    _WARN_SEEN_SCRIPT,
    _gate_key,
)

__all__ = [
    "DEFAULT_REQUIRED",
    "MAX_REQUIRED",
    "ADVISORY_REFERENCES",
    "decide_severity",
    "decide_read_severity",
    "find_precondition",
    "applies",
    "enforce_level",
    "has_warn_seen_marker",
    "precondition_script",
    "precondition_next_action",
]


ADVISORY_REFERENCES: tuple[ReferenceReadPrecondition, ...] = ()


# Canonical set of launch preconditions. New gate = one extra entry
# (open for extension). ``MAX_REQUIRED`` caps the gate so it stays
# targeted rather than a universal read-receipt mechanism.
# Bumped to 7 to make room for dynamically-added
# :class:`AdvisoryEchoPrecondition` instances (one per advisory with
# ``user_echo_required=True``); the static catalogue below still only
# carries 4 entries.
MAX_REQUIRED = 7
DEFAULT_REQUIRED: tuple[AnyPrecondition, ...] = (
    Precondition(
        name="detect_doc_state",
        script="util/detect-doc-state.py",
        why_blocking="required before --phase launch for category=spec",
        shim_flags="",
        # Opt in because ``util/detect-doc-state.py`` argparse accepts
        # ``--gate-id`` (see its ``main()`` — a reserved pass-through
        # flag that cache-hit payloads echo as ``cached_for_gate_id``).
        gate_id_flag_accepted=True,
    ),
    ReferenceReadPrecondition(
        name="read_pre_flight_protocol",
        reference_rel_path="sdd-common/references/pre-flight-protocol.md",
        why_blocking="pre-flight protocol must be read before --phase launch",
    ),
    ReferenceReadPrecondition(
        name="read_review_approval_pipeline",
        reference_rel_path="sdd-common/references/review-approval-pipeline.md",
        why_blocking="review-approval-pipeline reference drives approval CLI usage",
    ),
    PostChangeReviewPrecondition(),
)

assert len(DEFAULT_REQUIRED) <= MAX_REQUIRED, (
    "DEFAULT_REQUIRED exceeds MAX_REQUIRED — keep the launch gate targeted"
)


def applies(
    pre: AnyPrecondition,
    *, category: str,
    scope: str = SCOPE_PER_DOCUMENT,
    workflow_mode: str = "create",
) -> bool:
    """Scope guard — delegates to the precondition's own ``applies``."""
    return pre.applies(category=category, scope=scope, workflow_mode=workflow_mode)


def decide_severity(
    entries: Iterable[reference_ledger.LedgerEntry],
    *,
    category: str,
    target_name: str,
    project_path: str = "",
) -> str:
    """One-session warn→error cutover.

    * First ``launch`` call for this spec with a missing precondition →
      ``warn`` (a ``warn_seen`` marker is appended by the caller).
    * Any subsequent call in the same session → ``error``.
    """
    for entry in entries:
        if entry.script == _WARN_SEEN_SCRIPT:
            return "error"
    return "warn"


def _read_warn_seen_script(pre: ReferenceReadPrecondition) -> str:
    """Per-reference warn-seen marker — keeps new read requirements from
    retroactively blocking specs that pre-date the requirement."""
    return _gate_key("launch_preconditions.read_warn_seen", pre.name)


def decide_read_severity(
    entries: Iterable[reference_ledger.LedgerEntry],
    *,
    pre: ReferenceReadPrecondition,
    category: str,
    target_name: str,
    project_path: str = "",
) -> str:
    """One-session warn→error cutover for reference-read preconditions.

    Same shape as :func:`decide_severity` but keyed per precondition so
    each newly-required reference rolls out independently.
    """
    marker = _read_warn_seen_script(pre)
    for entry in entries:
        if entry.script == marker:
            return "error"
    return "warn"


def enforce_level(
    pre: AnyPrecondition,
    entries: list[reference_ledger.LedgerEntry],
    *,
    category: str,
    target_name: str,
    project_path: str,
) -> str:
    """Decide severity for a missing precondition — delegates to the
    precondition's own ``enforce_level``."""
    return pre.enforce_level(
        entries,
        category=category, target_name=target_name,
        project_path=project_path,
    )


def has_warn_seen_marker(
    pre: AnyPrecondition,
    entries: list[reference_ledger.LedgerEntry],
) -> bool:
    """Return True when this precondition has a prior warn-seen marker."""
    return pre.has_warn_seen_marker(entries)


def precondition_script(pre: AnyPrecondition, *, gate_id: str) -> str:
    """Resolve the ledger ``script`` key for a precondition.

    Post-change-review is keyed by ``gate_id`` (prompt is per-gate, not
    per spec); other types carry their script id on the dataclass.
    """
    if isinstance(pre, PostChangeReviewPrecondition):
        from .types import post_change_review_script_id
        return post_change_review_script_id(gate_id)
    if isinstance(pre, AdvisoryEchoPrecondition):
        return pre.script
    return pre.script


def precondition_next_action(
    pre: AnyPrecondition,
    *, category: str, target_name: str, project_path: str, gate_id: str,
) -> str:
    """Build the recovery ``next_action_command`` for a precondition.

    Every :class:`AnyPrecondition` subtype implements the unified
    ``next_action_command`` signature, so the dispatcher is branch-free.
    """
    return pre.next_action_command(
        category=category, target_name=target_name,
        project_path=project_path, gate_id=gate_id,
    )


def find_precondition(
    name: str,
    required: Iterable[AnyPrecondition] = DEFAULT_REQUIRED,
) -> "AnyPrecondition | None":
    """Return the precondition whose ``name`` matches — ``None`` when
    unknown. Callers dispatch on type after receiving a :class:`Finding`."""
    for pre in required:
        if pre.name == name:
            return pre
    return None
