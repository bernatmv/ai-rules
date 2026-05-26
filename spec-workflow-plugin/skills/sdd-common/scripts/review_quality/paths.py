"""Path resolution utilities for script and template discovery."""

import os

from sdd_core.output import safe_open  # noqa: F401 — re-exported for consumers

_SCRIPTS_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def script_path(name: str) -> str:
    return os.path.join(_SCRIPTS_ROOT, name)
