"""Launch preconditions gate — public facade.

Before ``--phase launch`` advances the gate it verifies that every
MUST-READ / MUST-RUN precondition recorded in
``sdd_core/reference_ledger`` has been satisfied for the current spec.

Design contract
---------------

* ``check(ctx, required) -> list[Finding]``: pure function; never mutates
  gate state. The caller decides whether to block or attach findings as
  warnings (one-session warn-only window).
* Findings carry ``next_action_command`` — the exact shim command the
  agent should run to satisfy the precondition.
* The warn→error cutover is driven by a prior ``_WARN_SEEN`` ledger
  entry written on the first offence; ``decide_severity`` encodes the
  single-session window deterministically.

Submodule layout (import-stable facade — every symbol is re-exported):
  * ``types``   — dataclasses, skills-root resolver.
  * ``policy``  — severity decisions + ``DEFAULT_REQUIRED`` catalogue.
  * ``ledger``  — ledger marker writers.
  * ``payload`` — ``check``, ``build_missing_payload``, etc.
"""
from __future__ import annotations

from .ledger import (
    advisory_echoed_script_id,
    mark_advisory_echoed,
    mark_post_change_review_acked,
    mark_post_change_review_presented,
    mark_read_warn_seen,
    mark_warn_seen,
    post_change_review_presented_script_id,
    post_change_review_script_id,
    read_post_change_review_presented,
)
from .payload import (
    build_ack_reference_read_command,
    build_missing_payload,
    build_pre_launch_sequence,
    build_required_reference_reads,
    check,
)
from .policy import (
    DEFAULT_REQUIRED,
    MAX_REQUIRED,
    decide_read_severity,
    decide_severity,
    find_precondition,
    has_warn_seen_marker,
)
from .types import (
    AdvisoryEchoPrecondition,
    Finding,
    PostChangeReviewPrecondition,
    Precondition,
    ReferenceReadPrecondition,
    _skills_root,
)

__all__ = [
    "Finding",
    "Precondition",
    "ReferenceReadPrecondition",
    "PostChangeReviewPrecondition",
    "AdvisoryEchoPrecondition",
    "DEFAULT_REQUIRED",
    "MAX_REQUIRED",
    "check",
    "decide_severity",
    "decide_read_severity",
    "build_ack_reference_read_command",
    "build_missing_payload",
    "build_pre_launch_sequence",
    "build_required_reference_reads",
    "find_precondition",
    "has_warn_seen_marker",
    "mark_warn_seen",
    "mark_read_warn_seen",
    "mark_post_change_review_acked",
    "mark_post_change_review_presented",
    "read_post_change_review_presented",
    "mark_advisory_echoed",
    "post_change_review_script_id",
    "post_change_review_presented_script_id",
    "advisory_echoed_script_id",
]


def __getattr__(name: str):
    # Convenience re-export for tests and ad-hoc callers that reference
    # ``_SKILLS_ROOT`` by name. Resolve lazily so ``SDD_SKILLS_ROOT``
    # overrides remain effective when accessed at runtime.
    if name == "_SKILLS_ROOT":
        return _skills_root()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
