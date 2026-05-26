"""Spec document I/O, section extraction, and structural validation.

This module re-exports all public symbols from doc_validation (validation,
phase detection) alongside spec listing/filtering. Existing callers that
import from sdd_core.specs continue to work unchanged.
"""
from __future__ import annotations

from pathlib import Path

from . import paths as _paths
from .doc_config import DOCUMENT_REGISTRY as _DOCUMENT_REGISTRY
from .matchers import WordMatcher
from .text import extract_sections

BUG_FIX_WORDS = WordMatcher(
    ["fix", "bugfix", "hotfix", "patch", "issue"],
    boundary="delimited",
)


def is_bug_fix_spec(spec_name: str) -> bool:
    """Return True if *spec_name* matches the canonical bug-fix word list.

    Single source of truth for bug-fix spec detection. Consumed by
    ``spec/detect-type.py`` and ``sdd_core.requirements_validation``.
    """
    if not spec_name:
        return False
    return spec_name in BUG_FIX_WORDS

from .doc_validation import (  # noqa: F401
    SpecPhase,
    SpecStatus,
    DOC_NAMES,
    DEFAULT_DOC_CHECKS,
    OPTIONAL_DOC_CHECKS,
    ValidationIssue,
    ValidationResult,
    merge_validation_results,
    read_spec_doc,
    find_section_by_keyword,
    validate_spec_structure,
    detect_spec_phase,
    PHASE_NOT_FOUND, PHASE_REQUIREMENTS, PHASE_UI_DESIGN,
    PHASE_DESIGN, PHASE_TASKS, PHASE_IMPLEMENTATION, PHASE_COMPLETED,
    STATUS_NOT_FOUND, STATUS_NOT_STARTED, STATUS_PENDING_APPROVAL,
    STATUS_IN_PROGRESS, STATUS_COMPLETED,
)

__all__ = [
    "DOC_NAMES",
    "DEFAULT_DOC_CHECKS",
    "SpecPhase",
    "SpecStatus",
    "PHASE_NOT_FOUND", "PHASE_REQUIREMENTS", "PHASE_UI_DESIGN",
    "PHASE_DESIGN", "PHASE_TASKS", "PHASE_IMPLEMENTATION", "PHASE_COMPLETED",
    "STATUS_NOT_FOUND", "STATUS_NOT_STARTED", "STATUS_PENDING_APPROVAL",
    "STATUS_IN_PROGRESS", "STATUS_COMPLETED",
    "ValidationIssue",
    "ValidationResult",
    "merge_validation_results",
    "read_spec_doc",
    "extract_sections",
    "find_section_by_keyword",
    "validate_spec_structure",
    "detect_spec_phase",
    "list_specs",
    "BUG_FIX_WORDS",
    "is_bug_fix_spec",
]


def list_specs(root: Path) -> list[str]:
    """List all spec directory names under .spec-workflow/specs/."""
    specs_root = root / _paths.WORKFLOW_DIR / "specs"
    if not specs_root.is_dir():
        return []
    return sorted(d.name for d in specs_root.iterdir() if d.is_dir())
