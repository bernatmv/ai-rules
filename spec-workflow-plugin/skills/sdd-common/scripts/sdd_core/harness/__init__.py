"""Harness adapter package — single abstraction for host-specific behaviour.

Every host-specific rendering goes through a :class:`HarnessAdapter`;
pipeline code loads one via :func:`loader.load_adapter` and calls
adapter methods. Three adapters ship today — Cursor, standard Claude
Code, and the Claude Code Task variant. New harnesses add one adapter
class and one :data:`registry.ADAPTERS` entry; no call-site changes
are required.
"""
from __future__ import annotations

from .adapter import (
    HarnessAdapter,
    PipelineTodo,
    PromptOption,
    PromptSpec,
    SelfcheckResult,
    SubAgentDispatchHints,
)
from .loader import (
    HarnessNotDetectedError,
    detect_adapter_strict,
    load_adapter,
    load_state,
    try_load_adapter,
)
from .detectors import HarnessContradictionError, PROBE_HARNESS_RESET_BARE
from .registry import ADAPTERS, available_adapter_names, get_adapter
from . import detectors  # noqa: F401 — registers built-in detectors.

# Canonical reset recovery command. Detectors emit the bare form so
# layers without a shim can still read it; workspace-health advisories
# apply the shim prefix so agents can copy-paste.
PROBE_HARNESS_RESET_COMMAND = f".spec-workflow/sdd {PROBE_HARNESS_RESET_BARE}"

__all__ = [
    "HarnessAdapter",
    "PipelineTodo",
    "PromptOption",
    "PromptSpec",
    "SelfcheckResult",
    "SubAgentDispatchHints",
    "HarnessContradictionError",
    "HarnessNotDetectedError",
    "PROBE_HARNESS_RESET_BARE",
    "PROBE_HARNESS_RESET_COMMAND",
    "load_adapter",
    "try_load_adapter",
    "detect_adapter_strict",
    "load_state",
    "ADAPTERS",
    "available_adapter_names",
    "get_adapter",
]
