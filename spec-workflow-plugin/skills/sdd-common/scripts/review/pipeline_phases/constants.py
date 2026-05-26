"""Module-level constants shared across pipeline phase handlers.

``__all__`` on the package barrel re-exports these names so callers can
import them from either location.

Phase names, envelope keys, advisory levels/codes, and the ``--phase``
flag literal are owned by :mod:`review.envelope_keys` (a true leaf
module) and re-exported here. The leaf prevents an import cycle
between :mod:`review._routing` and the package init, while keeping
``pipeline_phases.constants`` as the canonical reading surface for
phase handlers.
"""
from __future__ import annotations

from typing import Final

from ..envelope_keys import (  # noqa: F401  (re-exported)
    ADVISORY_CODE_ABANDONED_PRIOR_GATE,
    ADVISORY_CODE_CURSOR_ADVANCED,
    ADVISORY_CODE_LAUNCH_PRECONDITIONS_WARN,
    ADVISORY_CODE_PROMPT_REGISTRY_MISSING,
    ADVISORY_CODE_PROMPT_REGISTRY_UNKNOWN_TYPE,
    ADVISORY_CODE_REFERENCE_ACKS_CLEARED,
    ADVISORY_LEVEL_ERROR,
    ADVISORY_LEVEL_INFO,
    ADVISORY_LEVEL_WARN,
    KEY_ADVISORIES,
    KEY_LAST_COMPLETED_PHASE,
    KEY_LAST_COMPLETED_USER_CHOICE,
    KEY_NEXT_OPTIONS,
    NEXT_OPTIONS_KEY_COMMAND_TEMPLATE,
    NEXT_OPTIONS_KEY_COMMAND_WITH_RECOMMENDED,
    NEXT_OPTIONS_KEY_RATIONALE,
    NEXT_OPTIONS_KEY_USER_CHOICE_ENUM,
    NEXT_OPTIONS_KEY_USER_CHOICE_EXCLUDED,
    NEXT_OPTIONS_KEY_USER_CHOICE_RECOMMENDED,
    PHASE_ACK_CALLS,
    PHASE_CHECK_REVALIDATION,
    PHASE_FLAG,
    PHASE_POST_FIX,
    PHASE_POST_REVIEW,
    PHASE_PRE_APPROVAL,
)


SINGLE_DOC_KEYS: Final[frozenset[str]] = frozenset({
    "requirements.md", "ui-design.md", "design.md", "tasks.md",
})
"""Spec-document filenames that participate in ``per-document`` scoping.

Used by ``complete.py`` and ``pre_approval.py`` to recognise when a
just-completed gate reviewed exactly one spec doc. Membership-test only
— order is irrelevant, hence ``frozenset`` over ``tuple``.
"""


WARN_ENVELOPE_PAYLOAD_KEYS: Final[tuple[str, ...]] = (
    "missing_preconditions",
    "next_action_sequence",
    "next_action_command_sequence",
    "next_action_steps",
    KEY_ADVISORIES,
)
"""Keys lifted from ``build_missing_payload`` onto the warn-path launch
envelope. ``progress_checklist`` / ``progress_instruction`` are excluded
because the launch result already owns those names for the review-gate
checklist.
"""


# Why: the clean-advance chain emitted by post_fix.py is a load-bearing
# label for telemetry consumers and tests; the literal lives here so
# the chain emitter and any reader compare against the same constant.
POST_FIX_CLEAN_ADVANCE_LABEL: Final[str] = "post-fix-clean-advance"

# Trivial-advance chain shared by post_review (zero-findings) and
# post_fix (proceed-without-modifications). Single owner so both
# emitters stamp identical telemetry labels and operator-facing
# instructions onto the envelope — telemetry readers compare a single
# string, the operator reads the same sentence in both phases.
TRIVIAL_ADVANCE_LABEL: Final[str] = "trivial_advance_to_pre_approval"

TRIVIAL_ADVANCE_INSTRUCTION: Final[str] = (
    "Execute `next_action_command_sequence` in a single Bash "
    "turn. The chain acks pending tool calls, runs "
    "check-revalidation, and lands on pre-approval — three "
    "deterministic transitions become one observable command."
)
