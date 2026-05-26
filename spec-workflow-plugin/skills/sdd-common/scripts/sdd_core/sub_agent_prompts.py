"""Helpers for cross-repo sub-agent prompt construction.

The sub-agent sandbox in workspace operations may permit writes to a
sibling repo while denying reads. To keep the dispatch path safe, the
*parent* agent (which has full filesystem access) reads the listed
target-repo files and embeds them inline as a structured block via
:func:`build_target_repo_facts`. The block is substituted into the
prompt template as ``{target_repo_facts}``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from ._coerce import coerce_path

__all__ = [
    "build_target_repo_facts",
    "PROMPT_TRUNCATE_LINES",
    "DEFAULT_REPO_DOC_KINDS",
]


# Names of the root-level meta-docs every cross-repo handshake touches.
# Surfaced as a public constant so future sub-agent helpers can inherit
# the convention by ``Read``-ing this module.
DEFAULT_REPO_DOC_KINDS: tuple[str, ...] = (
    "CLAUDE.md",
    "DEVELOP.md",
    "AGENTS.md",
    "README.md",
)

# Truncation cap for embedded target-repo doc snippets — keeps a hostile
# repo from blowing the prompt budget. Surface as public so a sibling
# helper can co-pin the limit.
PROMPT_TRUNCATE_LINES = 80


def _read_truncated(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"_(could not read: {exc})_"
    lines = text.splitlines()
    if len(lines) > PROMPT_TRUNCATE_LINES:
        head = "\n".join(lines[:PROMPT_TRUNCATE_LINES])
        return head + "\n…(truncated)"
    return "\n".join(lines)


def build_target_repo_facts(
    repo_path: "str | os.PathLike[str]",
    *,
    doc_kinds: Iterable[str] = DEFAULT_REPO_DOC_KINDS,
) -> str:
    """Return a markdown block of target-repo facts the sub-agent can rely on.

    Each requested *doc_kind* surfaces as a ``### {filename}`` section. A
    missing file appears as ``### {filename} (not found)`` rather than
    raising — the sub-agent prompt should never fail on optional context.
    Each section truncates to 80 lines so a hostile target repo cannot
    blow the prompt budget.
    """
    root = coerce_path(repo_path, field_name="repo_path")
    sections: list[str] = []
    for kind in doc_kinds:
        target = root / kind
        header = f"### {kind}"
        if not target.is_file():
            sections.append(f"{header} (not found)")
            continue
        body = _read_truncated(target)
        sections.append(f"{header}\n\n```\n{body}\n```")
    return "\n\n".join(sections)
