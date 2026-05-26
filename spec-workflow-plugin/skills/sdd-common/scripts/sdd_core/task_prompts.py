"""Canonical task-prompt prefix + lifecycle suffix constants.

Single source of truth for the scaffolding every ``_Prompt:`` block in
a ``tasks.md`` must carry. The renderer (template tooling) and the
validator (``spec/lint-tasks.py`` Tier 1 check) import the same
constants so any drift surfaces as a single test failure.
"""
from __future__ import annotations

__all__ = [
    "TASK_PROMPT_PREFIX_FORMAT",
    "TASK_LIFECYCLE_SUFFIX_FORMAT",
    "render_task_prompt_prefix",
    "render_task_lifecycle_suffix",
]


TASK_PROMPT_PREFIX_FORMAT = "Implement the task for spec {spec_name}: "


TASK_LIFECYCLE_SUFFIX_FORMAT = (
    "\n\n"
    "Before starting implementation: (1) mark this task as in_progress by "
    "changing [ ] to [-] in tasks.md. (2) Search existing Implementation "
    "Logs for reusable code under `.spec-workflow/impl-log/{spec_name}/`. "
    "After implementation and testing: (3) call "
    "`.spec-workflow/sdd util/log-implementation.py` to record what was done "
    "— this MUST succeed before proceeding. "
    "(4) Only after log-implementation succeeds, mark the task complete by "
    "changing [-] to [x] in tasks.md."
)


def render_task_prompt_prefix(spec_name: str) -> str:
    """Return the canonical prefix with ``{spec_name}`` substituted."""
    return TASK_PROMPT_PREFIX_FORMAT.format(spec_name=spec_name)


def render_task_lifecycle_suffix(spec_name: str) -> str:
    """Return the canonical 4-step lifecycle suffix for *spec_name*."""
    return TASK_LIFECYCLE_SUFFIX_FORMAT.format(spec_name=spec_name)
