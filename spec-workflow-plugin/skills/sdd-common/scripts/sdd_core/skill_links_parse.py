"""Markdown text analysis for SDD skill link verification.

Pure text-in / structured-data-out operations: regex-based reference
extraction, prose line iteration (skipping frontmatter/code blocks),
and prefix table parsing.  Zero disk I/O beyond reading the target file.

This module's public surface is package-internal — its symbols are
prefixed with ``_`` because external callers should reach for
:mod:`sdd_core.skill_links` (which re-exports the high-level helpers).
The names below are exported here so the package's CI invariant
(`tests/test_sdd_core_all_strict`) sees a non-empty ``__all__``.
"""
from __future__ import annotations

__all__ = [
    "_MD_LINK_RE",
    "_BACKTICK_PATH_RE",
    "_TABLE_PATH_RE",
    "_SCRIPT_INVOCATION_RE",
    "_build_path_alternatives",
    "_iter_prose_lines",
    "_is_skippable",
    "_extract_refs",
    "_parse_prefix_table",
]

import re

from .matchers import WordMatcher
from .paths import COMMON_SKILL_NAME, ide_skills_prefixes

_MD_LINK_RE = re.compile(r"\[(?:[^\]]*)\]\(([^)\s]+)\)")

_KNOWN_EXTENSIONS = WordMatcher(("py", "md", "json"))
_EXT_PATTERN = r"\." + _KNOWN_EXTENSIONS.pattern_fragment()


def _build_path_alternatives(char_class: str) -> str:
    """Build the alternation group for all known path prefix patterns."""
    repo_abs = "|".join(re.escape(p) for p in ide_skills_prefixes())
    return "|".join([
        rf"\$SKILLS/{char_class}+{_EXT_PATTERN}",
        rf"\$SCRIPTS/{char_class}+{_EXT_PATTERN}",
        rf"@consumer/{char_class}+{_EXT_PATTERN}",
        rf"(?:{repo_abs})/{char_class}+{_EXT_PATTERN}",
        rf"(?:\.\.\/)+{char_class}+{_EXT_PATTERN}",
        rf"(?:references|scripts)/{char_class}+{_EXT_PATTERN}",
    ])


_BACKTICK_PATH_RE = re.compile(
    r"`(" + _build_path_alternatives(r"[^`\s{}()\[\]]") + r")`"
)

_TABLE_PATH_RE = re.compile(
    r"\|\s*(" + _build_path_alternatives(r"[^\s|]") + r")\s*\|"
)

_COMMON_SCRIPTS_ESCAPED = re.escape(f"$SKILLS/{COMMON_SKILL_NAME}/scripts/")

_SCRIPT_INVOCATION_RE = re.compile(
    r"(?:"
    rf"(?:python3?\s+){_COMMON_SCRIPTS_ESCAPED}"
    r"|"
    r"(?:python3?\s+-m\s+sdd_core\s+)(?:--project\s+\S+\s+)?"
    r"|"
    rf"\$SDD\s+(?:--project\s+\S+\s+)?(?:{_COMMON_SCRIPTS_ESCAPED})?"
    r"|"
    rf"\.spec-workflow/sdd\s+(?:--project\s+\S+\s+)?(?:{_COMMON_SCRIPTS_ESCAPED})?"
    r")"
    r"([^\s\"'`]+)"
)


def _iter_prose_lines(filepath):
    """Yield (lineno, line) tuples, skipping frontmatter, code blocks, and noverify."""
    with open(filepath) as f:
        lines = f.readlines()
    in_frontmatter = False
    in_code_block = False
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if lineno == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if "<!-- noverify -->" in line:
            continue
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        yield lineno, line



def _is_skippable(path: str) -> bool:
    if not path:
        return True
    if path.startswith(("http://", "https://", "mailto:")):
        return True
    if path.startswith("#"):
        return True
    if "{" in path:
        return True
    return False


def _extract_refs(line):
    """Extract all path references from a line. Yields (raw_path, kind)."""
    seen = set()
    for m in _MD_LINK_RE.finditer(line):
        raw = m.group(1).split("#")[0]
        if not _is_skippable(raw) and raw not in seen:
            seen.add(raw)
            yield raw, "md-link"
    for m in _BACKTICK_PATH_RE.finditer(line):
        raw = m.group(1)
        if not _is_skippable(raw) and raw not in seen:
            seen.add(raw)
            yield raw, "backtick"
    for m in _TABLE_PATH_RE.finditer(line):
        raw = m.group(1)
        if not _is_skippable(raw) and raw not in seen:
            seen.add(raw)
            yield raw, "table-cell"



def _parse_prefix_table(conventions_path: str) -> set[str]:
    """Extract prefix column values from the Prefix Reference markdown table."""
    prefixes: set[str] = set()
    in_table = False
    with open(conventions_path) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("| Prefix"):
                in_table = True
                continue
            if in_table and stripped.startswith("|---"):
                continue
            if in_table and stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|")]
                if len(cells) >= 2:
                    raw = cells[1]
                    is_deprecated = "~~" in raw
                    raw = raw.replace("~~", "").strip("`").strip()
                    if not raw or is_deprecated:
                        continue
                    if raw.startswith("("):
                        prefixes.add("(bare)")
                    else:
                        prefixes.add(raw)
            else:
                if in_table:
                    break
    return prefixes
