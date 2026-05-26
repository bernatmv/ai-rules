"""Phase Protocol + auto-discovery.

A *phase* is the runtime contract that backs one entry in
``sdd_core/data/workflow-graph.json``. The graph entry says **what** the
phase consumes / produces / fires; this package says **how** — each
``<phase_id>.py`` module under here implements the :class:`Phase`
Protocol from :mod:`.types` and is discovered by id at load time.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

from .types import Phase, Validator, ValidatorResult

if TYPE_CHECKING:  # pragma: no cover — typing-only
    from types import ModuleType

__all__ = [
    "Phase",
    "Validator",
    "ValidatorResult",
    "discover_phase",
    "discover_phases",
]


def discover_phase(phase_id: str) -> "ModuleType | None":
    """Return the module under :mod:`sdd_core.pipeline_phases` whose
    filename matches *phase_id* (with hyphens stripped).

    Returns ``None`` when no matching module exists — callers decide
    whether the missing module is fatal (graph-driven dispatch) or
    optional (lint-only resolution check).
    """
    module_name = phase_id.replace("-", "_")
    full = f"{__name__}.{module_name}"
    try:
        return importlib.import_module(full)
    except ModuleNotFoundError:
        return None


def discover_phases() -> dict[str, "ModuleType"]:
    """Return ``{phase_id: module}`` for every concrete phase module.

    Each module under :mod:`sdd_core.pipeline_phases` (other than
    ``types`` and modules starting with ``_``) is imported and indexed
    by its module-level ``id`` attribute. Modules without an ``id`` are
    skipped silently — they are library helpers, not dispatchable
    phases.
    """
    found: dict[str, "ModuleType"] = {}
    for info in pkgutil.iter_modules(__path__):
        name = info.name
        if name.startswith("_") or name == "types":
            continue
        module = importlib.import_module(f"{__name__}.{name}")
        phase_id = getattr(module, "id", None)
        if isinstance(phase_id, str) and phase_id:
            found[phase_id] = module
    return found
