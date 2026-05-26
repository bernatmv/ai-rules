"""Harness-state loader — resolves the active :class:`HarnessAdapter`.

The loader consults the detector registry in :mod:`detectors`. "No
signal" resolves through the safe-default detector with a warning.
Contradictions (bad override, malformed state, failed selfcheck) surface
as ``output.error`` envelopes.

Two entry points:

- :func:`load_adapter` — resolves the active adapter; explicit
  contradictions exit via ``output.error``.
- :func:`detect_adapter_strict` — raises
  :class:`HarnessNotDetectedError` when resolution falls through to
  the safe-default detector.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from sdd_core import output, paths

from .adapter import HarnessAdapter
from .detectors import (
    DetectionContext,
    HarnessContradictionError,
    resolve_detection,
)
from .registry import get_adapter

__all__ = [
    "HARNESS_STATE_FILENAME",
    "HARNESS_STATE_DIR",
    "HarnessNotDetectedError",
    "load_state",
    "load_adapter",
    "try_load_adapter",
    "detect_adapter_strict",
    "harness_state_path",
    "persist_state",
]


# Aliased so callers that imported this constant directly keep working.
# The canonical owner is :data:`sdd_core.paths.STATE_DIR_NAME` — no
# parallel literal lives here. Removing this alias is a future cleanup
# once every importer migrates to ``paths.STATE_DIR_NAME``.
HARNESS_STATE_DIR = paths.STATE_DIR_NAME
HARNESS_STATE_FILENAME = "harness.json"


class HarnessNotDetectedError(RuntimeError):
    """Raised by :func:`detect_adapter_strict` when no strong signal fires."""


def harness_state_path(project_path: str = "") -> str:
    """Resolve the canonical ``harness.json`` path.

    Persists under ``<project>/.spec-workflow/.sdd-state/harness.json``
    so it is cross-category (one harness per checkout). Routes through
    :func:`sdd_core.paths.workflow_state_path` so a future rename of
    ``.sdd-state`` flows through one symbol.
    """
    return paths.workflow_state_path(HARNESS_STATE_FILENAME, project_path)


def load_state(project_path: str = "") -> Optional[dict]:
    """Read-only helper: return parsed ``harness.json`` or ``None``.

    Raises :class:`HarnessNotDetectedError` on malformed content so
    callers can translate to envelopes via ``sdd_core.cli.run_main``.
    """
    path = harness_state_path(project_path)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessNotDetectedError(
            f"Harness state at {path} is unreadable ({exc}). Rerun "
            f"`util/probe-harness.py`."
        ) from exc
    if not isinstance(data, dict):
        raise HarnessNotDetectedError(
            f"Harness state at {path} is not a JSON object."
        )
    return data


def _build_detection_context(project_path: str) -> DetectionContext:
    return DetectionContext(
        project_path=project_path or "",
        env=dict(os.environ),
        state_path=harness_state_path(project_path),
    )


def persist_state(adapter_name: str, project_path: str) -> None:
    """Persist ``harness.json`` for *adapter_name* under *project_path*.

    Idempotent: writing the same name is a no-op. Every writer (loader
    auto-heal, workspace init, pipeline-tick) routes through here so
    the harness-state-file shape has a single writer.
    """
    # Local import — ``state`` imports :func:`harness_state_path` from
    # this module, so we defer until call time to keep the top-level
    # import graph acyclic.
    from .state import build_state, write_state

    state = build_state(
        adapter_name,
        probe_method="loader-auto",
        include_capabilities=False,
    )
    try:
        write_state(state, project_path)
    except OSError:
        pass


_WARN_ONCE_SOURCES = {"safe_default", "env_marker"}


def _should_warn(project_path: str, source: str) -> bool:
    """Return True iff no state file has been persisted for this source."""
    if source not in _WARN_ONCE_SOURCES:
        return True
    return not os.path.isfile(harness_state_path(project_path))


def _resolve_via_registry(project_path: str):
    ctx = _build_detection_context(project_path)
    outcome = resolve_detection(ctx)
    adapter = get_adapter(outcome.adapter_name)
    should_warn = _should_warn(project_path, outcome.source)
    if outcome.persist:
        persist_state(outcome.adapter_name, project_path)
    if outcome.warn and should_warn:
        output.warn(outcome.warn)
    return adapter, outcome


def load_adapter(project_path: str = "") -> HarnessAdapter:
    """Return the active adapter via the detector registry.

    Explicit contradictions surface through ``output.error`` (which
    exits the process); the function only returns on successful
    resolution. Weak signals (env marker, safe default) emit
    ``output.warn`` but still return an adapter.
    """
    try:
        adapter, _outcome = _resolve_via_registry(project_path)
        return adapter
    except HarnessContradictionError as exc:
        output.error(
            exc.message,
            hint=exc.hint,
            next_action_command=exc.next_action_command,
        )


def try_load_adapter(project_path: str = "") -> HarnessAdapter:
    """Return the active adapter, propagating ``HarnessContradictionError``.

    Mirrors :func:`load_adapter` but lets callers catch contradictions
    narrowly instead of terminating the process. Use in auto-dismiss
    paths (``ack-calls``, workspace health advisories) that want to
    degrade gracefully on a malformed state file.
    """
    adapter, _outcome = _resolve_via_registry(project_path)
    return adapter


def detect_adapter_strict(project_path: str = "") -> HarnessAdapter:
    """Return the active adapter only on a strong signal.

    Raises :class:`HarnessNotDetectedError` when resolution falls
    through to the safe-default detector. Contradictions propagate as
    :class:`detectors.HarnessContradictionError`.
    """
    adapter, outcome = _resolve_via_registry(project_path)
    if outcome.source == "safe_default":
        raise HarnessNotDetectedError(
            "No strong harness signal detected. Run "
            "`util/probe-harness.py` or set SDD_HARNESS_OVERRIDE."
        )
    return adapter
