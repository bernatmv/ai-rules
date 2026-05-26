#!/usr/bin/env python3
"""Lint SKILL.md bash-fenced examples for parallel-batch hygiene.

Surfaces two cascade-cancel pitfalls documented in
`$SKILLS/sdd-common/references/parallel-batch-hygiene.md`:

1. ``;``-chained existence probes (``test -f …``) with no trailing
   ``|| true`` or enclosing ``{ … ; } || true`` — the tail exit code
   cancels the whole parallel batch.
2. ``cat`` invocations with a concrete (non-variable) path — skill
   examples should model the ``Read`` tool for fixed-path reads.

Usage:
  internal_lints/skill_md_batch_hygiene.py --path <file.md>
  internal_lints/skill_md_batch_hygiene.py --all
  internal_lints/skill_md_batch_hygiene.py --baseline
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path

from sdd_core import cli
from internal_lints._skill_md_lint_cli import run_skill_md_lint

__sdd_manifest__ = {
    "summary": "SKILL.md bash-example batch-hygiene lint",
    "verbs": [
        "--path <file.md>",
        "--all",
        "--baseline",
    ],
    "flags": ["--path", "--all", "--baseline", "--workspace"],
}


_FENCE_RE = re.compile(r"^```(\w+)?\s*$")
# Markers that flag a bash block as a demonstrative anti-example —
# reference docs use blocks like "Wrong:" / "Anti-example:" to teach
# the correct form. The lint skips the block that follows such a
# marker so pedagogy does not count as a violation.
_ANTI_EXAMPLE_MARKERS = (
    "wrong",
    "anti-example",
    "antiexample",
    "anti-pattern",
    "antipattern",
    "counter-example",
    "counterexample",
    "do not",
    "don't",
    "dont",
    "incorrect",
    "never",
)
_TEST_F_RE = re.compile(r"\btest\s+-f\b")
# ``cat <concrete-path>`` — excludes shell-variable / subshell args
# (``$var``, ``"$var"``, ``<<EOF``, ``$(...)``). Matches any path-like
# argument that starts with a letter, dot, or slash.
_CAT_CONCRETE_PATH_RE = re.compile(
    r"(?:^|[\s;&|])cat\s+(?![-\$])[A-Za-z0-9./_\-]+"
)
_OR_TRUE_RE = re.compile(r"\|\|\s*true\b")

_PATTERNS_PATH = (
    Path(__file__).resolve().parent.parent
    / "sdd_core" / "data" / "batch_hygiene_patterns.yaml"
)


def _load_patterns() -> list[dict]:
    """Load and compile pattern rows from ``batch_hygiene_patterns.yaml``.

    Failures (missing file, malformed YAML, missing optional yaml dep)
    return ``[]`` so the lint degrades gracefully on environments
    without PyYAML — the hard-coded checks still fire.
    """
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return []
    try:
        text = _PATTERNS_PATH.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return []
    rows = data.get("patterns") or []
    compiled: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        regex = row.get("regex")
        if not regex:
            continue
        try:
            row_re = re.compile(regex)
        except re.error:
            continue
        compiled.append({
            "kind": str(row.get("kind") or "batch_hygiene_pattern"),
            "regex": row_re,
            "message": str(row.get("message") or "").strip(),
            "requires": [re.compile(r) for r in row.get("requires") or []],
            "forbids": [re.compile(r) for r in row.get("forbids") or []],
        })
    return compiled


_PATTERN_ROWS = _load_patterns()


def _is_anti_example_marker(text_line: str) -> bool:
    """Return True when ``text_line`` labels a following block as wrong.

    Matches common demonstrative prefixes (``Wrong:``, ``Anti-example``,
    ``# Wrong``, ``Don't:``) regardless of punctuation.
    """
    compacted = text_line.strip().lower().lstrip("#").strip()
    if not compacted:
        return False
    compacted = compacted.rstrip(".:—-")
    return compacted in _ANTI_EXAMPLE_MARKERS


def _iter_bash_blocks(text: str):
    """Yield ``(start_line_idx, lines)`` for each bash-fenced block.

    Blocks whose immediately preceding non-empty markdown line matches
    :data:`_ANTI_EXAMPLE_MARKERS` are skipped — the doc has already
    labelled the snippet as demonstrative.
    """
    lines_all = text.splitlines()
    in_block = False
    block_start = -1
    current: list[tuple[int, str]] = []
    skip_block = False
    for idx, line in enumerate(lines_all):
        fence = _FENCE_RE.match(line.strip())
        if fence:
            if in_block:
                if not skip_block:
                    yield block_start, current
                in_block = False
                current = []
                skip_block = False
                continue
            lang = (fence.group(1) or "").lower()
            if lang in ("bash", "sh", "shell", "zsh"):
                in_block = True
                block_start = idx + 1
                current = []
                # Look back for a demonstrative label on the nearest
                # non-empty previous line.
                skip_block = False
                j = idx - 1
                while j >= 0 and not lines_all[j].strip():
                    j -= 1
                if j >= 0 and _is_anti_example_marker(lines_all[j]):
                    skip_block = True
            continue
        if in_block:
            if not skip_block:
                # Inline marker comments (``# wrong``) guard the block
                # even when the Markdown context does not label it.
                if _is_anti_example_marker(line):
                    skip_block = True
            current.append((idx, line))
    if in_block and current and not skip_block:
        yield block_start, current


_TOOL_MAP = {
    "cat": "Read",
    "head": "Read",
    "tail": "Read",
    "sed": "StrReplace / Edit",
    "awk": "Read + Python",
    "echo": "Write / StrReplace",
}


def _first_token(stripped: str) -> str:
    """Return the first whitespace-delimited token, stripping leading
    subshell / redirect noise (``$()``, ``<(``) before the command."""
    cleaned = stripped
    # Strip a leading ``{ `` or ``(`` group prefix.
    while cleaned and cleaned[0] in "{(":
        cleaned = cleaned[1:].lstrip()
    # Strip a leading env-var assignment like ``FOO=bar cmd ...``
    tokens = cleaned.split()
    if tokens and "=" in tokens[0] and not tokens[0].startswith("-"):
        tokens = tokens[1:]
    return tokens[0] if tokens else ""


def _violations_for_block(
    path: Path,
    lines: list[tuple[int, str]],
    cfg: dict,
    forbidden_cfg: dict,
) -> list[dict]:
    out: list[dict] = []
    test_chain_required = bool(cfg.get("test_chain_requires_or_true", True))
    forbid_cat = bool(cfg.get("forbid_example_cat", True))
    forbidden_tokens = {
        str(t).strip().lower()
        for t in (forbidden_cfg.get("tokens") or ())
        if t
    }

    for idx, raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if test_chain_required:
            test_hits = list(_TEST_F_RE.finditer(stripped))
            chain_count = stripped.count(";") + stripped.count("&&")
            if len(test_hits) >= 2 and chain_count >= 1:
                if not _OR_TRUE_RE.search(stripped):
                    out.append({
                        "file": str(path),
                        "line": idx + 1,
                        "kind": "test_chain_missing_or_true",
                        "snippet": stripped,
                        "message": (
                            "Chained ``test -f`` probes exit with the "
                            "last command's status — append ``|| true`` "
                            "or wrap in ``{ ...; } || true`` so a "
                            "missing file does not cancel the batch."
                        ),
                    })
        if forbid_cat and _CAT_CONCRETE_PATH_RE.search(stripped):
            out.append({
                "file": str(path),
                "line": idx + 1,
                "kind": "example_uses_cat",
                "snippet": stripped,
                "message": (
                    "Skill examples should model the ``Read`` tool for "
                    "fixed-path reads instead of ``cat <path>``. See "
                    "`$SKILLS/sdd-common/references/parallel-batch-"
                    "hygiene.md` § Rule 4."
                ),
            })
        if forbidden_tokens:
            first = _first_token(stripped).lower()
            if first in forbidden_tokens:
                replacement = _TOOL_MAP.get(first, "the native tool")
                out.append({
                    "file": str(path),
                    "line": idx + 1,
                    "kind": "forbidden_bash_tool",
                    "snippet": stripped,
                    "message": (
                        f"Bash example leads with ``{first}`` — "
                        f"prefer {replacement}. See "
                        "`$SKILLS/sdd-common/references/tool-patterns.md` "
                        "§ Tool Choice for Common Needs."
                    ),
                })
        for row in _PATTERN_ROWS:
            if not row["regex"].search(stripped):
                continue
            if any(not r.search(stripped) for r in row["requires"]):
                continue
            if any(r.search(stripped) for r in row["forbids"]):
                continue
            out.append({
                "file": str(path),
                "line": idx + 1,
                "kind": row["kind"],
                "snippet": stripped,
                "message": row["message"],
            })
    return out


def lint_file(path: Path, rules: dict) -> list[dict]:
    cfg = (rules or {}).get("batch_hygiene") or {}
    forbidden_cfg = (rules or {}).get("forbidden_bash_tools") or {}
    if not cfg and not forbidden_cfg:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    violations: list[dict] = []
    for _block_start, lines in _iter_bash_blocks(text):
        violations.extend(_violations_for_block(
            path, lines, cfg, forbidden_cfg,
        ))
    return violations


def main() -> None:
    run_skill_md_lint(
        rule_label="batch-hygiene",
        lint_file=lint_file,
        include_references=True,
        script_name="internal_lints/skill_md_batch_hygiene.py",
    )


if __name__ == "__main__":
    cli.run_main(main)
