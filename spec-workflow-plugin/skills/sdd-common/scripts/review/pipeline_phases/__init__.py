"""Shared utilities for pipeline phase handlers.

Thin barrel module — re-exports from focused sub-modules to preserve the
existing import interface used by all phase handlers. Public names are
enumerated in :data:`__all__`.

Package import triggers the ``@phase`` decorator side-effect for every
non-private ``*.py`` sibling under this directory, populating
:data:`review.phase_kit._REGISTRY`. The decorator registry is the only
source of truth for "what is a phase" and package import is the only
side-effect that populates it.

The routing / snapshot / replay vocabulary (``route_with_ack``,
``maybe_append_ack_calls``, ``replay_snapshot``) lives exclusively in
:mod:`review._routing`. This barrel keeps only the guard, command,
scoring, and template re-exports owned by :mod:`review.pipeline_phases`.
"""
from __future__ import annotations

from .constants import (  # noqa: F401  (re-exported)
    PHASE_ACK_CALLS,
    PHASE_CHECK_REVALIDATION,
    PHASE_PRE_APPROVAL,
    POST_FIX_CLEAN_ADVANCE_LABEL,
    SINGLE_DOC_KEYS,
    WARN_ENVELOPE_PAYLOAD_KEYS,
)
from .templates import get_templates, VERIFICATION_PATHS, SUB_AGENT_BOUNDARY  # noqa: F401
from .guards import (  # noqa: F401
    phase_entry_guard,
    check_phase_sequence,
    check_pending_calls,
    attach_todo_calls,
    persist_pending_calls,
    ack_reference_reads_uses_batched,
)
from .commands import build_phase_cmd, build_prompt_cmd, resolve_skill_path  # noqa: F401
from .scoring_io import (  # noqa: F401
    read_artifact_score, read_scoped_score,
    count_effective_lines, load_quality_data, quality_file_path,
)


__all__ = (
    # Shared constants
    "PHASE_ACK_CALLS",
    "PHASE_CHECK_REVALIDATION",
    "PHASE_PRE_APPROVAL",
    "POST_FIX_CLEAN_ADVANCE_LABEL",
    "SINGLE_DOC_KEYS",
    "WARN_ENVELOPE_PAYLOAD_KEYS",
    # Re-exports from focused sub-modules
    "get_templates", "VERIFICATION_PATHS", "SUB_AGENT_BOUNDARY",
    "phase_entry_guard", "check_phase_sequence", "check_pending_calls",
    "attach_todo_calls", "persist_pending_calls",
    "ack_reference_reads_uses_batched",
    "build_phase_cmd", "build_prompt_cmd", "resolve_skill_path",
    "read_artifact_score", "read_scoped_score",
    "count_effective_lines", "load_quality_data", "quality_file_path",
)


# ---------------------------------------------------------------------------
# @phase side-effect import loop
# ---------------------------------------------------------------------------

# Import every non-private phase module so its ``@phase`` decorator
# populates :data:`review.phase_kit._REGISTRY` at package import time.
# Placed at the foot of the module so the re-exports above are already
# installed — a phase module that reaches back via ``from . import
# SUB_AGENT_BOUNDARY`` sees the barrel's public surface without
# ordering hazards.
from pathlib import Path as _Path
from importlib import import_module as _import_module

for _entry in sorted(_Path(__file__).resolve().parent.iterdir()):
    if not _entry.is_file() or _entry.suffix != ".py":
        continue
    if _entry.stem.startswith("_") or _entry.stem == "__init__":
        continue
    _import_module(f"review.pipeline_phases.{_entry.stem}")

del _Path, _import_module, _entry
