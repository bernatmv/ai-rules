"""Unified approval CLI facade.

Three entry-point scripts (``approval/request.py``,
``approval/update-status.py``, ``approval/delete.py``) all accept a
small overlapping set of flags with slightly different names. This
module is the single source of truth so:

* flag synonyms normalise consistently (``--status approved`` →
  ``approve``);
* extraneous flags are *echoed back* in the JSON success payload as
  ``ignored_flags`` instead of being silently ignored (callers may not
  re-read stderr for informational notes);
* the canonical action is echoed back so downstream reporting is
  unambiguous.

The façade is intentionally additive: every pre-existing invocation
shape remains valid. The three scripts keep their own ``argparse``
parsers (some exercise the positional variant). This module provides
the shared vocabulary.

Submodule layout (import-stable facade):
  * ``actions`` — canonical action list + aliases.
  * ``context`` — ``ApprovalContext``, id resolution, normalisation.
  * ``cli``     — argparse registration.
"""
from __future__ import annotations

from .actions import (
    ACTION_ALIASES,
    CANONICAL_ACTIONS,
    STATUS_TRANSITIONS,
    canonical_action,
    status_choices,
)
from .cli import canonical_args, parse_and_resolve
from .context import (
    ApprovalContext,
    approval_id_from_path,
    derive_approval_id,
    resolve,
)

__all__ = [
    "ApprovalContext",
    "CANONICAL_ACTIONS",
    "ACTION_ALIASES",
    "STATUS_TRANSITIONS",
    "canonical_args",
    "parse_and_resolve",
    "resolve",
    "canonical_action",
    "derive_approval_id",
    "approval_id_from_path",
    "status_choices",
]
