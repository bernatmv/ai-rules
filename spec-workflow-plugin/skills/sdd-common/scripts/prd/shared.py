"""Shared constants and utilities for PRD validation scripts."""
from __future__ import annotations

import re

from sdd_core.text import extract_sections  # noqa: F401 — re-exported

WHEN_THEN_RE = re.compile(r"WHEN\b.*\bTHEN\b", re.IGNORECASE)

SENTENCE_END_RE = re.compile(r"[.!?]\s")

NFR_CATEGORIES = [
    "Performance",
    "Availability",
    "Scalability",
    "Security",
    "Data Consistency",
    "Observability",
]

NFR_CATEGORY_KEYS = [c.lower().replace(" ", "_") for c in NFR_CATEGORIES]


def count_sentences(text: str) -> int:
    """Count approximate number of sentences in text."""
    text = text.strip()
    if not text:
        return 0
    splits = SENTENCE_END_RE.split(text)
    non_empty = [s for s in splits if s.strip()]
    if text and not SENTENCE_END_RE.search(text) and text.strip():
        return 1
    return len(non_empty)


def check_nfr_presence(content: str) -> list[str]:
    """Check all 6 NFR categories are mentioned in content (substring scan).

    Used by readiness gates for lightweight presence validation. For stricter
    section-aware + placeholder detection, use prd.checks.check_nfr_categories.
    """
    issues: list[str] = []
    content_lower = content.lower()
    for cat in NFR_CATEGORIES:
        if cat.lower() not in content_lower:
            issues.append(f"NFR category '{cat}' not found")
    return issues


def extract_section(content: str, heading_pattern: str) -> str:
    """Extract content under a heading matching the pattern.

    Uses heading-level awareness to stop at same-level or higher headings.
    """
    lines = content.splitlines()
    capturing = False
    section_lines: list[str] = []
    heading_level = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_text = stripped.lstrip("#").strip().lower()
            if re.search(heading_pattern, heading_text):
                capturing = True
                heading_level = level
                continue
            elif capturing and level <= heading_level:
                break
        if capturing:
            section_lines.append(line)

    return "\n".join(section_lines)
