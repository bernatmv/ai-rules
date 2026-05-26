"""Envelope-shape constants shared by the routing layer and phase handlers.

Lives at the ``review/`` level (sibling of :mod:`review._routing`) and
imports nothing from elsewhere in :mod:`review`. This keeps it a true
leaf so :mod:`review._routing` can import these names at module scope
without triggering :mod:`review.pipeline_phases.__init__`'s phase-
decorator side-effect loop (which imports phase modules that in turn
import from ``_routing`` — the cycle the leaf module sidesteps).

:mod:`review.pipeline_phases.constants` re-exports every name here so
external callers see one canonical location.
"""
from __future__ import annotations

from typing import Final


# Top-level envelope keys.
KEY_NEXT_OPTIONS: Final[str] = "next_options"
KEY_ADVISORIES: Final[str] = "advisories"


# Sub-keys on the ``next_options`` block.
NEXT_OPTIONS_KEY_COMMAND_TEMPLATE: Final[str] = "command_template"
NEXT_OPTIONS_KEY_COMMAND_WITH_RECOMMENDED: Final[str] = "command_with_recommended"
NEXT_OPTIONS_KEY_USER_CHOICE_ENUM: Final[str] = "user_choice_enum"
NEXT_OPTIONS_KEY_USER_CHOICE_RECOMMENDED: Final[str] = "user_choice_recommended"
NEXT_OPTIONS_KEY_USER_CHOICE_EXCLUDED: Final[str] = "user_choice_excluded"
NEXT_OPTIONS_KEY_RATIONALE: Final[str] = "rationale"


# Advisory levels.
ADVISORY_LEVEL_INFO: Final[str] = "info"
ADVISORY_LEVEL_WARN: Final[str] = "warn"
ADVISORY_LEVEL_ERROR: Final[str] = "error"


# Advisory codes.
ADVISORY_CODE_LAUNCH_PRECONDITIONS_WARN: Final[str] = "launch_preconditions_warn"
ADVISORY_CODE_REFERENCE_ACKS_CLEARED: Final[str] = "reference_acks_cleared"
ADVISORY_CODE_PROMPT_REGISTRY_UNKNOWN_TYPE: Final[str] = "prompt_registry_unknown_type"
ADVISORY_CODE_PROMPT_REGISTRY_MISSING: Final[str] = "prompt_registry_missing"
# Renamed from ``cursor_advanced`` so the advisory copy never
# substring-matches a harness name (``cursor`` is an IDE we ship to).
# ``phase_advanced`` reads as workflow-position advancement —
# unambiguous regardless of which harness is reading the envelope.
ADVISORY_CODE_CURSOR_ADVANCED: Final[str] = "phase_advanced"
# Hard-block advisory: a launch attempt encountered a non-terminal
# prior gate whose gate_id disagrees with the caller. The agent must
# discard the prior gate (or pick a different gate-id) before retrying.
ADVISORY_CODE_ABANDONED_PRIOR_GATE: Final[str] = "abandoned_prior_gate"


# Gate-state cursor scalars. Each phase that closes an attestation
# tick writes its own name and the user-choice it ran under so
# downstream emitters (notably ``ack-calls``) can short-circuit a
# stale next-action loop.
KEY_LAST_COMPLETED_PHASE: Final[str] = "last_completed_phase"
KEY_LAST_COMPLETED_USER_CHOICE: Final[str] = "last_completed_user_choice"


# Argparse tokens.
PHASE_FLAG: Final[str] = "--phase"


# Phase name literals — duplicated here for the routing layer to use
# without pulling in the phases package. The pipeline_phases.constants
# module re-exports these so phase handlers continue to read them from
# their familiar location.
PHASE_ACK_CALLS: Final[str] = "ack-calls"
PHASE_CHECK_REVALIDATION: Final[str] = "check-revalidation"
PHASE_PRE_APPROVAL: Final[str] = "pre-approval"
PHASE_POST_FIX: Final[str] = "post-fix"
PHASE_POST_REVIEW: Final[str] = "post-review"
