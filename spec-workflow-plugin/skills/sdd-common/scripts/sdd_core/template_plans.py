"""Plan-validate-apply pipeline for template lifecycle edits.

Implements the best-practice "verifiable intermediate output" pattern
for high-risk template mutations (customize/reset/sync):

  1. ``build_plan()``    — construct a plan dict from inputs.
  2. ``validate_plan()`` — return a list of actionable errors or [].
  3. ``apply_plan()``    — execute the plan using atomic filesystem ops.

Plans are persisted as JSON (``template-plan.json``) via
``save_plan`` / ``load_plan`` so they can be reviewed, diffed, or replayed.

The schema is intentionally small; future actions can extend
``TEMPLATE_PLAN_ACTIONS`` without altering the public API.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from . import output
from .paths import WORKFLOW_DIR, rel_or_abs, template_filename, templates_dir
from .template_resolution import ALL_TEMPLATE_TYPES
from .template_sync import sync_defaults_to_workspace

__all__ = [
    "PLAN_SCHEMA_VERSION",
    "TEMPLATE_PLAN_ACTIONS",
    "build_plan",
    "load_plan",
    "save_plan",
    "validate_plan",
    "apply_plan",
]


PLAN_SCHEMA_VERSION = "1.0.0"

# Actions allowed in a template-plan.json.
#   - customize: copy default template → user-templates/ (fails if user file exists)
#   - reset:     delete user-template file (fails if missing)
#   - sync:      re-copy reference templates to workspace defaults
TEMPLATE_PLAN_ACTIONS: frozenset[str] = frozenset({"customize", "reset", "sync"})


def build_plan(
    *,
    template_type: str,
    action: str,
    root: Path,
    custom_fields: dict[str, Any] | None = None,
) -> dict:
    """Create a plan dict for the given action.

    Does *not* touch the filesystem; use :func:`validate_plan` and
    :func:`apply_plan` to verify and execute.
    """
    filename = template_filename(template_type) if template_type else ""
    default_path = templates_dir(root, user=False) / filename if filename else None
    user_path = templates_dir(root, user=True) / filename if filename else None

    plan: dict = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "action": action,
        "template_type": template_type,
        "source_path": rel_or_abs(default_path, root) if default_path else "",
        "target_path": rel_or_abs(user_path, root) if user_path else "",
        "sections": [],
        "custom_fields": custom_fields or {},
    }
    return plan


def save_plan(path: str | Path, plan: dict) -> None:
    """Write plan JSON atomically with schema_version verification."""
    output.atomic_write_json(str(path), plan, verify_key="schema_version")


def load_plan(path: str | Path) -> dict:
    """Read plan JSON; emits ``output.error`` on missing/malformed file."""
    try:
        data = output.safe_read_json(path, default=None)
    except ValueError as e:
        output.error(f"Invalid JSON in plan file: {e}")
        raise  # unreachable
    if data is None:
        output.error(f"Plan file not found: {path}")
    if not isinstance(data, dict):
        output.error(f"Plan file is not a JSON object: {path}")
    return data


def validate_plan(plan: dict, root: Path) -> list[str]:
    """Return a list of validation errors (empty list = valid).

    Checks:
      * required top-level fields present
      * schema_version matches
      * action is allowed
      * template_type is a known doc type (for non-sync actions)
      * filesystem preconditions for the action
    """
    errors: list[str] = []

    if not isinstance(plan, dict):
        return [f"Plan must be a JSON object (got {type(plan).__name__})"]

    for required in ("schema_version", "action", "template_type"):
        if required not in plan:
            errors.append(f"Missing required field: {required}")

    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        errors.append(
            f"Unsupported schema_version: {plan.get('schema_version')!r} "
            f"(expected {PLAN_SCHEMA_VERSION!r})"
        )

    action = plan.get("action")
    if action not in TEMPLATE_PLAN_ACTIONS:
        errors.append(
            f"Unknown action: {action!r} (allowed: {sorted(TEMPLATE_PLAN_ACTIONS)})"
        )
        return errors  # later checks depend on action being valid

    template_type = plan.get("template_type")

    if action == "sync":
        # sync does not require a specific template_type; filesystem state
        # (reference dir present) is checked at apply time.
        return errors

    if not template_type:
        errors.append(f"{action} requires template_type")
        return errors

    if template_type not in ALL_TEMPLATE_TYPES:
        errors.append(
            f"Unknown template_type: {template_type!r} "
            f"(valid: {', '.join(ALL_TEMPLATE_TYPES)})"
        )
        return errors

    filename = template_filename(template_type)
    user_path = templates_dir(root, user=True) / filename
    default_path = templates_dir(root, user=False) / filename

    if action == "customize":
        if user_path.is_file():
            errors.append(
                f"User template already exists: {rel_or_abs(user_path, root)}"
            )
        if not default_path.is_file():
            errors.append(
                f"Default template missing: {rel_or_abs(default_path, root)}"
            )
    elif action == "reset":
        if not user_path.is_file():
            errors.append(
                f"No user template to reset: {rel_or_abs(user_path, root)}"
            )

    return errors


def apply_plan(plan: dict, root: Path) -> dict:
    """Execute a plan that has already been validated.

    Returns a dict describing what happened. Raises nothing unusual —
    filesystem exceptions propagate to the caller (who should be using
    ``cli.run_main`` to convert them to structured JSON errors).
    """
    action = plan["action"]

    if action == "sync":
        result = sync_defaults_to_workspace(root)
        return {
            "action": action,
            "copied": list(result.copied),
            "warnings": list(result.warnings),
            "failed": list(result.failed),
        }

    template_type = plan["template_type"]
    filename = template_filename(template_type)
    user_path = templates_dir(root, user=True) / filename
    default_path = templates_dir(root, user=False) / filename

    if action == "customize":
        user_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(default_path), str(user_path))
        return {
            "action": action,
            "template_type": template_type,
            "source": rel_or_abs(default_path, root),
            "target": rel_or_abs(user_path, root),
        }

    if action == "reset":
        user_path.unlink()
        return {
            "action": action,
            "template_type": template_type,
            "deleted": rel_or_abs(user_path, root),
        }

    # Defensive: validate_plan should have blocked this.
    raise ValueError(f"Cannot apply unknown action: {action!r}")
