"""Command string builders for pipeline phase invocations."""
from __future__ import annotations

from typing import Optional

from sdd_core.skill_links_resolve import resolve_skills_prefix


def build_phase_cmd(
    phase: str,
    *,
    project_path: str,
    category: str,
    target_name: str,
    extra_args: str = "",
    lifecycle_flags: str = "",
) -> str:
    """Build a ``pipeline-tick.py`` invocation string for a given phase.

    Agent-facing CLI is always ``pipeline-tick`` (single verb). The
    ``--phase`` flag here is ``pipeline-tick``'s internal override —
    it tells the dispatcher which phase to forward to rather than
    reading the session's ``required_next_phase``.

    Extra phase-specific flags ride behind a ``--`` separator so the
    pipeline-tick locator parser forwards them verbatim to the
    resolved phase. ``lifecycle_flags`` (e.g.
    ``" --parent-todo X --gate-id Y"``) also flows through the
    separator.
    """
    parts = [
        ".spec-workflow/sdd review/pipeline-tick.py",
        f"--category {category}",
        f'--target-name "{target_name}"',
        f"--workspace {project_path}",
        f"--phase {phase}",
    ]
    tail: list[str] = []
    if extra_args:
        tail.append(extra_args)
    lifecycle_tail = lifecycle_flags.strip()
    if lifecycle_tail:
        tail.append(lifecycle_tail)
    # Lifecycle flags must reach the resolved phase, not the dispatcher.
    # Anything after ``--`` is forwarded verbatim by pipeline-tick to
    # ``prepare-pipeline.py <phase>``.
    if tail:
        parts.append("--")
        parts.extend(tail)
    return " ".join(parts)


def build_prompt_cmd(
    prompt_type: str,
    params: str,
    *,
    exclude_opts: Optional[list[str]] = None,
) -> str:
    """Build a generate-prompt.py invocation string."""
    parts = [
        ".spec-workflow/sdd util/generate-prompt.py",
        f"--type {prompt_type}",
        f"--params {params}",
    ]
    if exclude_opts:
        parts.append(f'--exclude-options {",".join(exclude_opts)}')
    return " ".join(parts)


def resolve_skill_path(review_skill: str) -> str:
    """Return the absolute ``SKILL.md`` path for *review_skill*.

    Routed through :func:`resolve_skills_prefix` so every sub-agent
    prompt uses the same expansion rule. A missing skills root raises
    ``FileNotFoundError`` (caller surfaces via ``output.error``) rather
    than silently composing an IDE-native fallback that the
    absolute-path lint would later reject.
    """
    return resolve_skills_prefix(f"$SKILLS/{review_skill}/SKILL.md")
