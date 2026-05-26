"""Template resolution, validation, and variable substitution.

Facade module — re-exports from focused sub-modules:
- template_resolution: find/resolve paths, list, reference dir
- template_sync: sync defaults, user-templates readme
- template_variables: substitution engine, default variables

Validation and diff remain inline (tightly coupled with resolution).
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import paths
from .matchers import WordMatcher
from .text import iter_stripped_lines

from .template_resolution import (  # noqa: F401 — re-exported
    ALL_TEMPLATE_TYPES,
    ResolvedTemplate,
    TemplateInfo,
    resolve_template,
    list_templates,
    get_reference_dir,
)
from .template_sync import (  # noqa: F401 — re-exported
    SyncResult,
    hash_template,
    sync_defaults_to_workspace,
    sync_user_templates_readme,
)
from .template_variables import (  # noqa: F401 — re-exported
    KNOWN_VARIABLES,
    VARIABLE_RE as _VARIABLE_RE,
    substitute_variables,
    get_default_variables,
)

__all__ = [
    "ALL_TEMPLATE_TYPES",
    "KNOWN_VARIABLES",
    "ResolvedTemplate",
    "TemplateValidationResult",
    "TemplateInfo",
    "SyncResult",
    "resolve_template",
    "validate_template",
    "substitute_variables",
    "get_default_variables",
    "list_templates",
    "get_reference_dir",
    "hash_template",
    "sync_defaults_to_workspace",
    "sync_user_templates_readme",
    "diff_template",
]


MIN_SECTIONS = 2
MIN_TEMPLATE_LINES = 5
MAX_TEMPLATE_LINES = 500

# Per-template heading expectations consumed by template validation.
# Promoted from a function-local dict to module-level constants so a
# future "headings drift" lint can hook the same registry.
# _TEMPLATE_SECTIONS intentionally differs from
# ``doc_config.expected_headings_for_stem``: doc_config defines
# headings expected in *finished documents* (used by review scoring),
# while these tuples define headings expected in *template files*
# (authoring scaffolding). Bug-fix types have no doc_config entry at
# all; the resolver fallback in :func:`_expected_sections_for` handles
# steering / ui-design types that share expectations between templates
# and documents.
_REQUIREMENTS_HEADINGS: tuple[str, ...] = (
    "Requirements", "Non-Functional Requirements",
)
_DESIGN_HEADINGS: tuple[str, ...] = (
    "Architecture", "Components and Interfaces", "Testing Strategy",
)
_BUG_FIX_REQUIREMENTS_HEADINGS: tuple[str, ...] = (
    "Bug Summary", "Reproduction Steps",
)
_BUG_FIX_DESIGN_HEADINGS: tuple[str, ...] = (
    "Root Cause Analysis", "Fix Approach",
)
# Workspace coordinator requirements add a Cross-Repo Scope section.
# ``Open Questions`` is intentionally omitted — it is "optional, delete
# if empty" exactly like the bug-fix variants.
_WORKSPACE_REQUIREMENTS_HEADINGS: tuple[str, ...] = (
    "Requirements", "Non-Functional Requirements", "Cross-Repo Scope",
)
# ``tasks`` / ``bug-fix-tasks`` carry no required headings — task
# scaffolding is generated rather than authored against a fixed shape.
_NO_TEMPLATE_HEADINGS: tuple[str, ...] = ()
_TEMPLATE_HEADINGS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "requirements": _REQUIREMENTS_HEADINGS,
    "design": _DESIGN_HEADINGS,
    "tasks": _NO_TEMPLATE_HEADINGS,
    "bug-fix-requirements": _BUG_FIX_REQUIREMENTS_HEADINGS,
    "bug-fix-design": _BUG_FIX_DESIGN_HEADINGS,
    "bug-fix-tasks": _NO_TEMPLATE_HEADINGS,
    "workspace-requirements": _WORKSPACE_REQUIREMENTS_HEADINGS,
}

_SELF_CLOSING_HTML_TAGS = WordMatcher(("br", "hr"))
_EMPTY_HTML_RE = _SELF_CLOSING_HTML_TAGS.compose(
    prefix=r"^\s*<",
    suffix=r"\s*/?>$",
)

_VALIDATORS: list[Callable[[str, str], tuple[list[str], list[str]]]] = []


def register_validator(fn: Callable[[str, str], tuple[list[str], list[str]]]):
    _VALIDATORS.append(fn)
    return fn


@dataclass
class TemplateValidationResult:
    """Named to avoid collision with sdd_core.specs.ValidationResult."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sections_found: list[str] = field(default_factory=list)
    sections_missing: list[str] = field(default_factory=list)
    unknown_variables: list[str] = field(default_factory=list)


@register_validator
def _check_non_empty(content: str, doc_type: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if not content.strip():
        errors.append("Template file is empty")
    return errors, warnings


@register_validator
def _check_top_level_heading(content: str, doc_type: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if not content.strip():
        return errors, warnings
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            if not stripped.startswith("# "):
                errors.append("Template must start with a top-level heading (# ...)")
            break
    return errors, warnings


@register_validator
def _check_section_count(content: str, doc_type: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    sections = [l for l in content.splitlines() if l.strip().startswith("## ")]
    if len(sections) < MIN_SECTIONS:
        errors.append(
            f"Template needs at least {MIN_SECTIONS} ## sections for compliance checks (found {len(sections)})"
        )
    return errors, warnings


@register_validator
def _check_unknown_variables(content: str, doc_type: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    found = set(_VARIABLE_RE.findall(content))
    unknown = found - KNOWN_VARIABLES
    if unknown:
        warnings.append(
            f"Unknown template variables: {', '.join(sorted(unknown))}. "
            f"Recognized: {', '.join(sorted(KNOWN_VARIABLES))}"
        )
    return errors, warnings


@register_validator
def _check_placeholder_guidance(content: str, doc_type: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if not re.search(r"\[(?![^\]]*\]\()[^\]]{2,}\]", content):
        warnings.append(
            "Template contains no bracket placeholders ([...]). "
            "Placeholders help authors know where to fill content."
        )
    return errors, warnings


@register_validator
def _check_no_html(content: str, doc_type: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if re.search(r"<script[\s>]", content, re.IGNORECASE):
        errors.append("Template contains <script> tags — security risk")
    if re.search(r"<(?!!)(?!/)[a-zA-Z][^>]*>", content) and not re.search(r"^```", content, re.MULTILINE):
        in_code_block = False
        for line in content.splitlines():
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
            elif not in_code_block and re.search(r"<(?!!)(?!/)[a-zA-Z][^>]*>", line):
                if not _EMPTY_HTML_RE.match(line):
                    errors.append("Template contains raw HTML outside code blocks — use pure markdown")
                    break
    return errors, warnings


@register_validator
def _check_reasonable_size(content: str, doc_type: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    line_count = len(content.splitlines())
    if line_count < MIN_TEMPLATE_LINES:
        warnings.append(f"Template is very short ({line_count} lines) — may not provide enough guidance")
    elif line_count > MAX_TEMPLATE_LINES:
        warnings.append(f"Template is very long ({line_count} lines) — consider trimming for usability")
    return errors, warnings


def validate_template(template_path: Path, doc_type: str) -> TemplateValidationResult:
    """Structural validation of a template file."""
    content = template_path.read_text(encoding="utf-8")

    all_errors: list[str] = []
    all_warnings: list[str] = []
    for validator in _VALIDATORS:
        errors, warnings = validator(content, doc_type)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    sections_found = [
        line.lstrip("# ").strip()
        for line in iter_stripped_lines(content)
        if line.startswith("## ")
    ]

    expected_sections = _expected_sections_for(doc_type)
    sections_missing = [s for s in expected_sections if s not in sections_found]

    unknown_vars = sorted(set(_VARIABLE_RE.findall(content)) - KNOWN_VARIABLES)

    return TemplateValidationResult(
        valid=len(all_errors) == 0,
        errors=all_errors,
        warnings=all_warnings,
        sections_found=sections_found,
        sections_missing=sections_missing,
        unknown_variables=unknown_vars,
    )


def _expected_sections_for(doc_type: str) -> list[str]:
    """Minimal expected sections per document type for *template* validation."""
    if doc_type in _TEMPLATE_HEADINGS_BY_TYPE:
        return list(_TEMPLATE_HEADINGS_BY_TYPE[doc_type])

    from .doc_config import expected_headings_for_stem
    for rtype in ("spec", "steering"):
        headings = expected_headings_for_stem(rtype, doc_type)
        if headings:
            return headings

    return []


def diff_template(doc_type: str, root: Path) -> str | None:
    """Generate unified diff between user-template and default template."""
    filename = paths.template_filename(doc_type)
    user_path = paths.templates_dir(root, user=True) / filename
    default_path = paths.templates_dir(root, user=False) / filename

    if not user_path.is_file():
        return None

    default_lines = []
    if default_path.is_file():
        default_lines = default_path.read_text(encoding="utf-8").splitlines(keepends=True)

    user_lines = user_path.read_text(encoding="utf-8").splitlines(keepends=True)

    diff = difflib.unified_diff(
        default_lines,
        user_lines,
        fromfile=f"templates/{filename}",
        tofile=f"user-templates/{filename}",
    )
    return "".join(diff)
