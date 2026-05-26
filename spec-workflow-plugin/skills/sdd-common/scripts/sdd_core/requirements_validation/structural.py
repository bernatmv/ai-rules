"""Structural (paragraph-level) rules for requirements.md.

Covers:
  * Required H2 heading presence.
  * ``As a …, I want …, so that …`` user-story shape.
  * ``WHEN/IF … THEN … SHALL`` acceptance-criterion shape.
  * ``## Requirement N`` sections must have body content.

These rules run on paragraphs rather than individual lines because the
user-story and acceptance-criterion shapes routinely wrap across soft
newlines — line-by-line matching gave false negatives.
"""
from __future__ import annotations

import re
from typing import Any

from ..matchers import WordMatcher
from ..text import extract_sections, iter_content_lines, iter_paragraphs
from ..validation_helpers import Severity
from .types import Finding

__all__ = ["structural_findings"]


_USER_STORY_RE = re.compile(
    r"(?:\*\*User\s+Story:?\*\*\s*)?As\s+an?\s+.+?,\s*I\s+want\s+.+?,\s*so\s+that\s+.+",
    re.IGNORECASE,
)
_ACCEPTANCE_RE = re.compile(
    r"(?:\bWHEN\b|\bIF\b).+?\bTHEN\b.+?\bSHALL\b",
    re.IGNORECASE,
)

# Marker matchers used for smarter error messages when the full
# paragraph-level regex fails. Reuses ``WordMatcher`` so marker detection
# stays consistent with the rest of the validator (no new alternation
# regex).
_USER_STORY_MARKER = WordMatcher(
    ["**User Story:**", "**User Story**"],
    boundary="none", case_sensitive=False,
)
_AC_MARKER = WordMatcher(
    ["WHEN", "THEN", "SHALL"],
    boundary="word", case_sensitive=True,
)


def _check_structural_paragraph(
    content: str, severity: str,
) -> list[Finding]:
    """Paragraph-level scan for user-story and acceptance-criterion rules.

    Single iteration over paragraphs (DRY) covers both structural rules.
    Paragraphs are obtained via :func:`iter_paragraphs` which collapses
    soft line-breaks — wrapped user stories / acceptance criteria now
    match, resolving the wrap footgun documented in the analysis report.
    """
    has_user_story = False
    has_ac = False
    for _start, paragraph in iter_paragraphs(content):
        if not has_user_story and _USER_STORY_RE.search(paragraph):
            has_user_story = True
        if not has_ac and _ACCEPTANCE_RE.search(paragraph):
            has_ac = True
        if has_user_story and has_ac:
            break

    findings: list[Finding] = []
    if not has_user_story:
        marker_hit = any(
            _USER_STORY_MARKER.search(raw)
            for _, raw, _ in iter_content_lines(content)
        )
        findings.append(Finding(
            severity=severity,
            group="structural",
            rule="user-story-present",
            line=1,
            column=1,
            section="Requirements",
            match="",
            message=(
                "Found '**User Story:**' marker but the full story "
                "'As a …, I want …, so that …' did not match on a single "
                "paragraph. Check for a missing clause or a blank line "
                "splitting the story."
                if marker_hit else
                "No user story found (format: 'As a [role], I want …, so that …')"
            ),
            suggestion=None,
        ))
    if not has_ac:
        marker_hit = any(
            _AC_MARKER.search(raw)
            for _, raw, _ in iter_content_lines(content)
        )
        findings.append(Finding(
            severity=severity,
            group="structural",
            rule="acceptance-criterion-present",
            line=1,
            column=1,
            section="Requirements",
            match="",
            message=(
                "Found WHEN/THEN/SHALL keyword(s) but no full acceptance "
                "criterion matched on a single paragraph. Check for a "
                "missing clause or a blank line splitting the criterion."
                if marker_hit else
                "No WHEN/IF … THEN … SHALL acceptance criterion found"
            ),
            suggestion=None,
        ))
    return findings


def structural_findings(content: str, ruleset: dict[str, Any]) -> list[Finding]:
    """Structural checks — headings, user stories, acceptance criteria, empty sections."""
    findings: list[Finding] = []
    group = ruleset["groups"].get("structural")
    if not group:
        return findings

    severity = Severity(group["default_severity"]).value
    sections = extract_sections(content)
    section_headings = {k.lower(): (k, v) for k, v in sections.items()}

    # headings-required
    required = ("Introduction", "Requirements", "Non-Functional Requirements")
    for heading in required:
        if not any(heading.lower() in k for k in section_headings):
            findings.append(Finding(
                severity=severity,
                group="structural",
                rule="headings-required",
                line=1,
                column=1,
                section="",
                match=heading,
                message=f"Missing required heading: '{heading}'",
                suggestion=None,
            ))

    findings.extend(_check_structural_paragraph(content, severity))

    # no-empty-requirement-sections
    for heading, body in sections.items():
        if re.match(r"^Requirement\s+\d+", heading.strip(), re.IGNORECASE):
            body_lines = [ln for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
            if not body_lines:
                findings.append(Finding(
                    severity=severity,
                    group="structural",
                    rule="no-empty-requirement-sections",
                    line=1,
                    column=1,
                    section=heading,
                    match=heading,
                    message=f"Requirement section '{heading}' has no body content",
                    suggestion=None,
                ))

    return findings
