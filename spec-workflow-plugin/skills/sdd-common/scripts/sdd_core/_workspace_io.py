"""Internal workspace I/O helpers shared by workspace_manifest and workspace_tracker."""
from __future__ import annotations

from pathlib import Path

from . import output, paths
from ._coerce import coerce_path
from .paths import COORDINATION_MANIFEST_FILENAME, WORKSPACE_TRACKER_FILENAME

_WORKSPACE_FILES = {
    "manifest": COORDINATION_MANIFEST_FILENAME,
    "tracker": WORKSPACE_TRACKER_FILENAME,
}


def find_by_key(items: list[dict], key: str, value: str) -> dict | None:
    """Find first dict in *items* where ``dict[key] == value``, or ``None``."""
    return next((item for item in items if item.get(key) == value), None)


def read_workspace_file(root: "Path | str", feature: str, kind: str) -> dict:
    if kind not in _WORKSPACE_FILES:
        raise ValueError(
            f"Unknown workspace file kind '{kind}'. "
            f"Valid kinds: {sorted(_WORKSPACE_FILES)}"
        )
    root = coerce_path(root)
    file_path = paths.workspace_dir(root, feature) / _WORKSPACE_FILES[kind]
    return output.safe_read_json(file_path, default={})


def write_workspace_file(root: "Path | str", feature: str, kind: str, content: dict) -> None:
    if kind not in _WORKSPACE_FILES:
        raise ValueError(
            f"Unknown workspace file kind '{kind}'. "
            f"Valid kinds: {sorted(_WORKSPACE_FILES)}"
        )
    root = coerce_path(root)
    file_path = paths.workspace_dir(root, feature) / _WORKSPACE_FILES[kind]
    output.atomic_write_json(str(file_path), content)


def pending_batch_path(
    root: Path, feature: str, batch_type: str,
) -> Path:
    """Return the canonical path for a pending batch file.

    ``batch_type`` is ``"approval"`` for whole-spec batch approvals and
    ``"phase-{doc}"`` (e.g. ``"phase-requirements"``) for per-phase
    approvals.
    """
    filename = f"pending-{batch_type}-batch.json"
    return paths.workspace_dir(root, feature) / filename


def require_workspace_file(root: "Path | str", feature: str, kind: str, hint: str = "") -> dict:
    """Read a workspace file or raise ``FileNotFoundError`` if missing/empty."""
    root = coerce_path(root)
    data = read_workspace_file(root, feature, kind)
    if not data:
        msg = f"No {kind} found for feature '{feature}'"
        raise FileNotFoundError(
            f"{msg}. {hint}" if hint
            else f"{msg}. Run the workspace workflow to create the {kind} first"
        )
    return data
