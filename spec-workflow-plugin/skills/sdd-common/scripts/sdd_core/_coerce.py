"""Path coercion helpers for the public ``sdd_core.*`` API surface.

Public functions whose first parameter accepts a workspace root
(``read_manifest``, ``read_tracker``, peers under
``sdd_core._workspace_io``, ``sdd_core.paths.*_dir``) accept ``str |
Path`` and coerce to :class:`pathlib.Path` via :func:`coerce_path`.
"""
from __future__ import annotations

import os
from pathlib import Path

__all__ = ["coerce_path"]


def coerce_path(value: object, *, field_name: str = "root") -> Path:
    """Return *value* as a :class:`Path`; raise on garbage input.

    Liskov-clean: callers that already pass ``Path`` see identity;
    callers that pass ``str`` are accepted; anything else raises
    ``TypeError`` with *field_name* in the message so the offending
    parameter is obvious from the traceback alone.
    """
    if isinstance(value, Path):
        return value
    if isinstance(value, (str, os.PathLike)):
        return Path(os.fspath(value))
    raise TypeError(
        f"{field_name!r} must be str or Path, got {type(value).__name__}"
    )
