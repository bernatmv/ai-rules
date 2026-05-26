"""Single writer for ``harness.json``.

Both the loader auto-heal path and the explicit
``util/probe-harness.py`` CLI route through :func:`write_state` so the
JSON shape, schema version, and atomic-write semantics live in one
place. :func:`build_state` is the paired constructor; adapters expose
their own capability vocabulary via :meth:`HarnessAdapter.capabilities`
so the probe does not branch on adapter name.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Mapping

from sdd_core.security.state import TransactionalStore

from .loader import harness_state_path
from .registry import get_adapter

__all__ = ["SCHEMA_VERSION", "build_state", "write_state"]

SCHEMA_VERSION = 1


def build_state(
    adapter_name: str,
    *,
    probe_method: str,
    include_capabilities: bool,
) -> dict:
    """Return the ``harness.json`` payload for *adapter_name*.

    ``include_capabilities=True`` inlines
    :meth:`HarnessAdapter.capabilities` so CLI probes surface the host
    capability map for downstream consumers; loader auto-heal writes
    skip the map because the loader only needs the adapter identity.
    """
    state: dict = {
        "schema_version": SCHEMA_VERSION,
        "harness": adapter_name,
        "detected_at": datetime.datetime.now(
            datetime.timezone.utc,
        ).isoformat(),
        "probe_method": probe_method,
    }
    if include_capabilities:
        state["capabilities"] = dict(get_adapter(adapter_name).capabilities())
    return state


def write_state(state: Mapping, project_path: str) -> str:
    """Atomically persist *state* at the canonical harness-state path."""
    path = harness_state_path(project_path)
    Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
    with TransactionalStore(path) as store:
        store.write_json(dict(state))
    return path
