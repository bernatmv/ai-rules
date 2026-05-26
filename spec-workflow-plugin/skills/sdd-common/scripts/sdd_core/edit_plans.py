"""Plan-validate-apply helpers for implementation multi-file edits.

Companion to :mod:`sdd_core.template_plans` for the implement-spec skill.
Used by ``impl/plan-task.py`` and ``impl/validate-plan.py``.

Schema (``edit-plan.json``)::

    {
      "schema_version": "1.0.0",
      "spec_name": "my-feature",
      "task_id": "3.2",
      "files": [
        {"path": "src/foo.py",     "action": "modify", "summary": "…",
         "size_delta_estimate": 42},
        {"path": "tests/test_foo.py", "action": "add", "summary": "…"}
      ],
      "acceptance_criteria": [...]
    }

Tasks that edit many files benefit from a verifiable intermediate
artifact: it makes reviews auditable, catches scope creep, and surfaces
gitignore violations before the filesystem is touched.
"""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from . import output
from .paths import is_under

__all__ = [
    "EDIT_PLAN_SCHEMA_VERSION",
    "EDIT_PLAN_ACTIONS",
    "DEFAULT_FILE_THRESHOLD",
    "DEFAULT_SIZE_DELTA_THRESHOLD",
    "build_plan",
    "load_plan",
    "save_plan",
    "validate_plan",
    "requires_plan",
]


EDIT_PLAN_SCHEMA_VERSION = "1.0.0"

# File-level actions an entry in ``files[]`` can declare.
EDIT_PLAN_ACTIONS: frozenset[str] = frozenset({"add", "modify", "delete", "rename"})

# Defaults; ``sdd-common/references/implementation-rules.md`` may override.
DEFAULT_FILE_THRESHOLD = 5
DEFAULT_SIZE_DELTA_THRESHOLD = 400  # lines


def requires_plan(
    file_count: int,
    *,
    threshold: int = DEFAULT_FILE_THRESHOLD,
) -> bool:
    """True when the task touches more than *threshold* files."""
    return file_count > threshold


def build_plan(
    *,
    spec_name: str,
    task_id: str,
    files: Iterable[dict] | None = None,
    acceptance_criteria: Iterable[str] | None = None,
) -> dict:
    """Construct a plan dict; no filesystem side effects."""
    return {
        "schema_version": EDIT_PLAN_SCHEMA_VERSION,
        "spec_name": spec_name,
        "task_id": task_id,
        "files": [dict(f) for f in (files or [])],
        "acceptance_criteria": list(acceptance_criteria or []),
    }


def save_plan(path: str | Path, plan: dict) -> None:
    """Atomic-write plan JSON with schema_version verification."""
    output.atomic_write_json(str(path), plan, verify_key="schema_version")


def load_plan(path: str | Path) -> dict:
    """Read plan JSON; emits ``output.error`` on missing/invalid file."""
    try:
        data = output.safe_read_json(path, default=None)
    except ValueError as e:
        output.error(f"Invalid JSON in edit plan: {e}")
        raise  # unreachable
    if data is None:
        output.error(f"Edit plan file not found: {path}")
    if not isinstance(data, dict):
        output.error(f"Edit plan is not a JSON object: {path}")
    return data


def _read_gitignore_patterns(root: Path) -> list[str]:
    """Read top-level ``.gitignore`` (if present) returning non-empty patterns.

    Intentionally simple: single-file, no recursive ``.gitignore`` chains.
    Catches the obvious mistakes (``.venv/``, ``node_modules/``, ``dist/``)
    without pulling in ``pathspec``.
    """
    gi = root / ".gitignore"
    if not gi.is_file():
        return []
    patterns: list[str] = []
    for raw in gi.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _matches_gitignore(rel_path: str, patterns: list[str]) -> bool:
    """Loose fnmatch-based gitignore check (top-level patterns only)."""
    posix = rel_path.replace(os.sep, "/")
    for pattern in patterns:
        pat = pattern.rstrip("/")
        if not pat:
            continue
        if fnmatch.fnmatch(posix, pat):
            return True
        # Directory-style: match any segment equal to the pattern
        # (e.g. ``.venv`` blocks ``.venv/lib/foo``).
        if "/" not in pat and any(seg == pat for seg in posix.split("/")):
            return True
    return False


def validate_plan(
    plan: dict,
    root: Path,
    *,
    size_delta_threshold: int = DEFAULT_SIZE_DELTA_THRESHOLD,
    allow_large_delta: bool = False,
) -> list[str]:
    """Validate a plan against workspace state.

    Checks:
      * required top-level fields
      * schema_version match
      * each file entry has path + allowed action
      * paths are relative and stay inside *root*
      * paths are not excluded by the top-level ``.gitignore``
      * ``size_delta_estimate`` does not exceed *size_delta_threshold*
        unless ``allow_large_delta`` is True
    """
    errors: list[str] = []
    if not isinstance(plan, dict):
        return [f"Plan must be a JSON object (got {type(plan).__name__})"]

    for required in ("schema_version", "spec_name", "task_id", "files"):
        if required not in plan:
            errors.append(f"Missing required field: {required}")

    if plan.get("schema_version") != EDIT_PLAN_SCHEMA_VERSION:
        errors.append(
            f"Unsupported schema_version: {plan.get('schema_version')!r} "
            f"(expected {EDIT_PLAN_SCHEMA_VERSION!r})"
        )

    files = plan.get("files") or []
    if not isinstance(files, list) or not files:
        errors.append("files[] is required and must be non-empty")
        return errors

    patterns = _read_gitignore_patterns(root)
    root_abs = root.resolve()

    seen: set[str] = set()
    for idx, entry in enumerate(files):
        if not isinstance(entry, dict):
            errors.append(f"files[{idx}] must be an object")
            continue

        path = entry.get("path")
        if not path or not isinstance(path, str):
            errors.append(f"files[{idx}].path is required")
            continue

        if path in seen:
            errors.append(f"Duplicate file path in plan: {path}")
        seen.add(path)

        if PurePosixPath(path).is_absolute() or path.startswith(os.sep):
            errors.append(f"files[{idx}].path must be relative: {path}")
            continue

        if ".." in path.replace("\\", "/").split("/"):
            errors.append(f"files[{idx}].path must not contain '..': {path}")
            continue

        resolved = (root / path).resolve()
        if not is_under(resolved, root_abs):
            errors.append(f"files[{idx}].path escapes project root: {path}")

        action = entry.get("action", "modify")
        if action not in EDIT_PLAN_ACTIONS:
            errors.append(
                f"files[{idx}].action {action!r} not in {sorted(EDIT_PLAN_ACTIONS)}"
            )

        if _matches_gitignore(path, patterns):
            errors.append(
                f"files[{idx}].path is excluded by .gitignore: {path}"
            )

        delta = entry.get("size_delta_estimate")
        if delta is not None:
            if not isinstance(delta, int):
                errors.append(
                    f"files[{idx}].size_delta_estimate must be an int (got {type(delta).__name__})"
                )
            elif delta > size_delta_threshold and not allow_large_delta:
                errors.append(
                    f"files[{idx}].size_delta_estimate={delta} exceeds "
                    f"threshold={size_delta_threshold}; rerun with "
                    f"allow_large_delta=true to acknowledge"
                )

    return errors
