#!/usr/bin/env python3
"""Shared utilities for SDD skill scripts.

This module is co-deployed with the scripts that import it. It serves as
a thin compatibility re-exporter: timestamp/text/IO helpers live in the
``sdd_core`` foundation package and are re-exported here so existing
imports (``from skill_helpers import ...``) keep working.
"""

import os
import sys

from sdd_core.time import ts_now, ts_short, ts_from_epoch  # noqa: F401
from sdd_core.text import iter_content_lines, iter_line_categories  # noqa: F401
from sdd_core.output import safe_open  # noqa: F401 — re-exported for consumers

__all__ = [
    "ts_now",
    "ts_short",
    "ts_from_epoch",
    "safe_open",
    "WALK_SKIP_DIRS",
    "find_md_files",
    "walk_all_files",
    "iter_effective_lines",
    "iter_meaningful_lines",
    "iter_line_categories",
]

WALK_SKIP_DIRS = frozenset({".venv", ".pytest_cache", "__pycache__", "node_modules", ".git"})


def _walk_files(root, predicate=None, skip_suffixes=None):
    """Base iterator: yield (rel_path, abs_path) for files under root."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in WALK_SKIP_DIRS)
        for fname in sorted(filenames):
            if skip_suffixes and any(fname.endswith(s) for s in skip_suffixes):
                continue
            if predicate and not predicate(fname):
                continue
            abs_path = os.path.join(dirpath, fname)
            yield os.path.relpath(abs_path, root), abs_path


def find_md_files(root: str):
    """Yield absolute paths of .md files under root."""
    for _, abs_path in _walk_files(root, predicate=lambda f: f.endswith(".md")):
        yield abs_path


def walk_all_files(root: str, skip_suffixes=None):
    """Yield (rel_path, abs_path) for all files under root."""
    yield from _walk_files(root, skip_suffixes=skip_suffixes)


def _iter_lines(filepath: str):
    """Core iterator: yield (lineno, raw, stripped) skipping frontmatter + code blocks."""
    with safe_open(filepath) as fh:
        content = fh.read()
    return ((i + 1, raw, stripped) for i, raw, stripped in iter_content_lines(content))


def iter_effective_lines(filepath: str):
    """Yield non-empty stripped lines, skipping frontmatter and code blocks."""
    for _, _, stripped in _iter_lines(filepath):
        if stripped:
            yield stripped


def iter_meaningful_lines(filepath: str):
    """Yield (lineno, raw_line) tuples, skipping frontmatter and code blocks.

    Unlike iter_effective_lines, this preserves line numbers and the original
    (unstripped) line text — useful for link verification and error reporting.
    """
    for lineno, raw, _ in _iter_lines(filepath):
        yield lineno, raw
