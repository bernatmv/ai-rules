"""Path resolution and fix logic for SDD skill link verification.

Maps raw path strings to disk locations, provides basename-indexed file
lookup for suggestions, rewrites non-canonical paths to the ``$SKILLS/``
prefix, and maintains the prefix registry (single source of truth for
_resolve_path + conventions).

External callers should reach for :mod:`sdd_core.skill_links`; the
private-prefixed names below are exported for the parent module's
re-export surface and for the CI invariant
``tests/test_sdd_core_all_strict``.
"""
from __future__ import annotations

__all__ = [
    "_FIX_CROSS_SKILL_RELATIVE_RE",
    "_FIX_REPO_ABS_RE",
    "_NOVERIFY_RE",
    "_CROSS_SKILL_RELATIVE_RE",
    "_get_file_index",
    "_suggest_fix",
    "_resolve_path",
    "fix_file",
    "_RESOLVE_REGISTRY",
    "_register_prefix",
    "_implemented_prefixes",
    "resolve_skills_prefix",
]

import functools
import os
import re

from .paths import (
    COMMON_SKILL_NAME,
    common_scripts_dir,
    find_skills_root,
    ide_skills_prefixes,
)

_FIX_CROSS_SKILL_RELATIVE_RE = re.compile(r"(?:\.\.\/)+(?=sdd-[a-z])")
_FIX_REPO_ABS_RE = re.compile(
    "|".join(re.escape(p + "/") for p in ide_skills_prefixes())
)
_NOVERIFY_RE = re.compile(r"\s*<!-- noverify -->")
_CROSS_SKILL_RELATIVE_RE = re.compile(r"(?:\.\.\/)+sdd-")


def _get_file_index(skills_root: str) -> dict[str, list[str]]:
    """Build a basename -> relative-path index for all files under skills_root."""
    index: dict[str, list[str]] = {}
    for dirpath, _, filenames in os.walk(skills_root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, skills_root)
            index.setdefault(fn, []).append(rel)
    return index



def _suggest_fix(rel_path: str, skills_root: str, file_index: dict[str, list[str]]) -> str | None:
    """Find closest matching file when a $SKILLS/ path is broken."""
    target_name = os.path.basename(rel_path)
    if not target_name:
        return None
    candidates = file_index.get(target_name, [])
    if len(candidates) == 1:
        return f"$SKILLS/{candidates[0]}"
    return None



def _resolve_path(raw_path, file_dir, skills_root, workspace_root):
    """Resolve a path reference to (abs_path | None, category, fix_suggestion | None)."""
    if raw_path.startswith("$SKILLS/"):
        rel = raw_path[len("$SKILLS/"):]
        return os.path.normpath(os.path.join(skills_root, rel)), "skills-prefix", None

    if raw_path.startswith("$SCRIPTS/"):
        rel = raw_path[len("$SCRIPTS/"):]
        resolved = os.path.normpath(
            os.path.join(str(common_scripts_dir(skills_root)), rel)
        )
        return resolved, "scripts-prefix", None

    if raw_path.startswith("@consumer/"):
        return None, "consumer", None

    for prefix in ide_skills_prefixes():
        dir_prefix = prefix + "/"
        if raw_path.startswith(dir_prefix):
            resolved = os.path.normpath(os.path.join(workspace_root, raw_path))
            fix = "$SKILLS/" + raw_path[len(dir_prefix):]
            return resolved, "repo-absolute", fix

    if _CROSS_SKILL_RELATIVE_RE.match(raw_path):
        resolved = os.path.normpath(os.path.join(file_dir, raw_path))
        parts = raw_path.split("/")
        sdd_idx = next(
            (i for i, p in enumerate(parts) if p.startswith("sdd-")), None
        )
        fix = "$SKILLS/" + "/".join(parts[sdd_idx:]) if sdd_idx is not None else None
        return resolved, "cross-skill-relative", fix

    if raw_path.startswith("../") or raw_path.startswith(
        ("references/", "scripts/")
    ):
        resolved = os.path.normpath(os.path.join(file_dir, raw_path))
        return resolved, "within-skill", None

    if raw_path.endswith((".md", ".py", ".json")):
        resolved = os.path.normpath(os.path.join(file_dir, raw_path))
        return resolved, "bare", None

    return None, "unknown", None



def fix_file(filepath):
    """Rewrite non-canonical skill paths in a single file.

    Returns ``(count, change_details)``. Non-canonical inputs include
    repo-absolute ``.cursor/skills/`` prefixes and ``../`` chains
    climbing out of a skill to reach a sibling — both are rewritten to
    the portable ``$SKILLS/`` form.
    """
    with open(filepath) as f:
        original_lines = f.readlines()

    fixed_lines = []
    for line in original_lines:
        new_line = _FIX_CROSS_SKILL_RELATIVE_RE.sub("$SKILLS/", line)
        new_line = _FIX_REPO_ABS_RE.sub("$SKILLS/", new_line)
        path_was_fixed = new_line != line
        if path_was_fixed:
            new_line = _NOVERIFY_RE.sub("", new_line)
        fixed_lines.append(new_line)

    fixed = "".join(fixed_lines)
    original = "".join(original_lines)

    if fixed == original:
        return 0, []

    changes = []
    orig_split = original.splitlines()
    fixed_split = fixed.splitlines()
    max_lines = max(len(orig_split), len(fixed_split))
    for i in range(max_lines):
        ol = orig_split[i] if i < len(orig_split) else ""
        nl = fixed_split[i] if i < len(fixed_split) else ""
        if ol != nl:
            changes.append({"line": i + 1, "before": ol.strip(), "after": nl.strip()})

    with open(filepath, "w") as f:
        f.write(fixed)

    return len(changes), changes


_RESOLVE_REGISTRY: dict[str, dict] = {}


def _register_prefix(prefix: str, category: str, *, equivalents: set[str] | None = None,
                      doc_skip: bool = False):
    """Register a prefix handled by _resolve_path.

    Parameters
    ----------
    prefix : str
        The prefix string (e.g. "$SKILLS/").
    category : str
        Resolution category returned by _resolve_path.
    equivalents : set[str] | None
        Other prefixes that are logically equivalent for convention comparison.
    doc_skip : bool
        If True, skip this prefix when checking doc-vs-code drift (for
        entries like "(bare)" that aren't real startswith prefixes in docs).
    """
    _RESOLVE_REGISTRY[prefix] = {
        "category": category,
        "equivalents": equivalents or set(),
        "doc_skip": doc_skip,
    }


_register_prefix("$SKILLS/", "skills-prefix")
_register_prefix("$SCRIPTS/", "scripts-prefix")
_register_prefix("@consumer/", "consumer")
_register_prefix("references/", "within-skill")
_register_prefix("../", "within-skill", equivalents={"../scripts/"})
_register_prefix("../scripts/", "within-skill", equivalents={"../"})
_register_prefix("(bare)", "bare", doc_skip=True)
_register_prefix(".spec-workflow/sdd", "shim", doc_skip=True)


# This module lives under ``$SKILLS/sdd-common/scripts/sdd_core/``
# so the skills root is three parents up. Provides a deterministic
# fall-back when :func:`find_skills_root` cannot resolve the project's
# own ``.cursor/skills`` — the running scripts always know where they
# were loaded from.
_OWN_SKILLS_ROOT = os.fspath(
    __import__("pathlib").Path(__file__).resolve().parents[3]
)


@functools.lru_cache(maxsize=32)
def _cached_skills_root(project_path: str) -> str:
    workspace = project_path or None
    try:
        return str(find_skills_root(workspace))
    except FileNotFoundError:
        return _OWN_SKILLS_ROOT


def resolve_skills_prefix(raw: str, *, project_path: str = "") -> str:
    """Expand ``$SKILLS/<name>/...`` into the absolute path callers read.

    Non-``$SKILLS/`` inputs are returned unchanged so call sites can
    funnel every cross-skill path through this helper without
    branching. Uses :func:`sdd_core.paths.find_skills_root` to probe
    the active IDE skills directory; falls back to the skills root
    that contains this module when the project tree has no
    ``.cursor/skills`` yet (cross-repo review targets).
    """
    if not raw.startswith("$SKILLS/"):
        return raw
    rel = raw[len("$SKILLS/"):]
    root = _cached_skills_root(project_path)
    return os.path.normpath(os.path.join(root, rel))


def _implemented_prefixes() -> set[str]:
    """Return the set of all registered prefixes."""
    return set(_RESOLVE_REGISTRY.keys())
