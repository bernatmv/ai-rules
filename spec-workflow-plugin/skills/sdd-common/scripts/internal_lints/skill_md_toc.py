#!/usr/bin/env python3
"""Lint SKILL.md files for Contents TOC completeness.

For each user-invocable SKILL.md:

  * Every ``## `` heading must appear in the ``## Contents`` TOC block.
  * Every ``[label](#slug)`` entry in the TOC must correspond to a
    ``## `` heading.
  * Headings must use title-case (lowercase linking words are allowed —
    title-case lint matches the subset of words that look like proper
    titles). Allowed parenthetical suffixes come from the YAML rule.

The TOC block is the span from the first ``## Contents`` line (or
``Contents``) to the next ``## `` heading.

Usage:
  internal_lints/skill_md_toc.py --path <SKILL.md>
  internal_lints/skill_md_toc.py --all
  internal_lints/skill_md_toc.py --baseline
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path

from sdd_core import cli
from sdd_core.text import iter_line_categories
from internal_lints._skill_md_lint_cli import run_skill_md_lint

__sdd_manifest__ = {
    "summary": "SKILL.md Contents-TOC completeness lint",
    "verbs": [
        "--path <skill.md>",
        "--all",
        "--baseline",
    ],
    "flags": ["--path", "--all", "--baseline", "--workspace"],
}


_HEADING_RE = re.compile(r"^##\s+(.*?)\s*$")
_TOC_LINK_RE = re.compile(r"\[([^\]]+)\]\(#[^)]+\)")


def _slugify(heading: str) -> str:
    normalized = heading.strip().lower()
    normalized = re.sub(r"[^a-z0-9\s-]", "", normalized)
    normalized = re.sub(r"\s+", "-", normalized)
    return normalized.strip("-")


def _collect_headings_and_toc(
    text: str,
) -> tuple[list[tuple[int, str]], list[tuple[int, str]], int]:
    """Return ``(headings, toc_entries, toc_start_line)``.

    ``headings`` are ``(line_index, heading_text)`` for every ``## `` line
    outside the TOC span. ``toc_entries`` are ``(line_index, label)`` for
    each linked entry in the ``## Contents`` block. ``toc_start_line`` is
    the line index of the ``## Contents`` heading, or ``-1`` when absent.
    """
    lines_with_cat = list(iter_line_categories(text))
    headings: list[tuple[int, str]] = []
    toc_entries: list[tuple[int, str]] = []
    toc_start = -1
    toc_end = -1
    # First pass: locate the TOC span.
    for i, raw, _stripped, cat in lines_with_cat:
        if cat != "effective":
            continue
        m = _HEADING_RE.match(raw)
        if not m:
            continue
        label = m.group(1).strip()
        if toc_start == -1 and label.lower() == "contents":
            toc_start = i
        elif toc_start != -1:
            toc_end = i
            break
    if toc_start == -1:
        toc_end = len(text.splitlines())
    elif toc_end == -1:
        toc_end = len(text.splitlines())

    for i, raw, _stripped, cat in lines_with_cat:
        if cat != "effective":
            continue
        m = _HEADING_RE.match(raw)
        if m:
            label = m.group(1).strip()
            if label.lower() == "contents":
                continue
            if toc_start != -1 and toc_start < i < toc_end:
                # Inside the TOC span headings are impossible by the
                # pass above (we stopped at the next ``## `` line), but
                # guard anyway.
                continue
            headings.append((i, label))
            continue
        if toc_start != -1 and toc_start < i < toc_end:
            for link_label in _TOC_LINK_RE.findall(raw):
                toc_entries.append((i, link_label.strip()))
    return headings, toc_entries, toc_start


_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")

# Linking words that may legitimately stay lowercase inside title-case
# headings (``Use the Adapter`` is still title case). Keeps the
# predicate in-module per best-practices § concise.
_TITLE_CASE_LOWERCASE_OK = frozenset({
    "a", "an", "and", "as", "at", "but", "by", "for", "in", "of",
    "on", "or", "the", "to", "vs", "with",
})


def _is_title_case(label: str) -> bool:
    """Return True iff every word in *label* is title-cased.

    Lowercase linking words (see :data:`_TITLE_CASE_LOWERCASE_OK`) are
    accepted anywhere except the first position. Non-alphabetic tokens
    (digits, ``—``, backticks) pass through.
    """
    words = label.split()
    if not words:
        return True
    for idx, word in enumerate(words):
        stripped = word.lstrip("`*_[(").rstrip("`*_)],.:;!?")
        if not stripped:
            continue
        lead = next((c for c in stripped if c.isalpha()), "")
        if not lead:
            continue
        if lead.isupper():
            continue
        if idx > 0 and stripped.lower() in _TITLE_CASE_LOWERCASE_OK:
            continue
        return False
    return True


def _normalize(label: str, allow_suffixes: list[str]) -> str:
    """Normalize a heading / TOC label for comparison.

    Strips the explicit allow-list suffixes first, then drops any
    trailing parenthetical group. Keeps the leading descriptive words
    so `"Workflow"` matches `"Workflow (Steps 1-8)"` without listing
    every step range in the YAML allow-list.
    """
    out = label.strip()
    for suf in allow_suffixes:
        if out.endswith(suf):
            out = out[: -len(suf)].strip()
    while True:
        stripped = _TRAILING_PAREN_RE.sub("", out).strip()
        if stripped == out:
            break
        out = stripped
    return out


def lint_file(path: Path, rules: dict) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    cfg = (rules or {}).get("toc_completeness") or {}
    if not cfg:
        return []
    allow_suffixes = list(cfg.get("allow_suffixes", []))

    headings, toc_entries, toc_start = _collect_headings_and_toc(text)
    if toc_start == -1:
        # No Contents section — skip rather than demand retrofits on
        # every SKILL.md. Files without a TOC opt in by adding one.
        return []
    violations: list[dict] = []

    normalized_headings = {
        _normalize(label, allow_suffixes): (line, label)
        for line, label in headings
    }
    normalized_toc = {
        _normalize(label, allow_suffixes): (line, label)
        for line, label in toc_entries
    }

    for norm, (line, raw_label) in normalized_headings.items():
        if norm not in normalized_toc:
            violations.append({
                "file": str(path),
                "line": line + 1,
                "kind": "heading_missing_from_toc",
                "heading": raw_label,
                "message": (
                    f"Heading {raw_label!r} missing from ## Contents TOC"
                ),
            })
    for norm, (line, raw_label) in normalized_toc.items():
        if norm not in normalized_headings:
            violations.append({
                "file": str(path),
                "line": line + 1,
                "kind": "toc_entry_missing_heading",
                "label": raw_label,
                "message": (
                    f"TOC entry {raw_label!r} has no matching ## heading"
                ),
            })

    if cfg.get("case") == "title":
        for line, raw_label in headings:
            stripped = _normalize(raw_label, allow_suffixes)
            if stripped and not _is_title_case(stripped):
                violations.append({
                    "file": str(path),
                    "line": line + 1,
                    "kind": "heading_not_title_case",
                    "heading": raw_label,
                    "message": (
                        f"Heading {raw_label!r} is not title-case"
                    ),
                })

    forbidden_chars = cfg.get("forbidden_characters") or []
    if forbidden_chars:
        forbidden_set = {
            entry.get("char", "") for entry in forbidden_chars
            if isinstance(entry, dict) and entry.get("char")
        }
        for line, raw_label in toc_entries:
            matched = [c for c in forbidden_set if c and c in raw_label]
            if matched:
                violations.append({
                    "file": str(path),
                    "line": line + 1,
                    "kind": "toc_forbidden_character",
                    "label": raw_label,
                    "message": (
                        f"TOC label {raw_label!r} contains forbidden "
                        f"character(s) {matched!r}"
                    ),
                })
    return violations


def main() -> None:
    run_skill_md_lint(
        rule_label="TOC-completeness",
        lint_file=lint_file,
        script_name="internal_lints/skill_md_toc.py",
    )


if __name__ == "__main__":
    cli.run_main(main)
