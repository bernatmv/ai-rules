"""Document heading validation, structure checks, and phase detection.

Split from specs.py for single-responsibility: callers that only need
list_specs() don't need to import the validation dependency graph.
"""
from __future__ import annotations

from pathlib import Path

__all__ = [
    "DEFAULT_DOC_CHECKS",
    "OPTIONAL_DOC_CHECKS",
    "PHASE_COMPLETED",
    "PHASE_DESIGN",
    "PHASE_IMPLEMENTATION",
    "PHASE_NOT_FOUND",
    "PHASE_REQUIREMENTS",
    "PHASE_TASKS",
    "PHASE_UI_DESIGN",
    "STATUS_COMPLETED",
    "STATUS_IN_PROGRESS",
    "STATUS_NOT_FOUND",
    "STATUS_NOT_STARTED",
    "STATUS_PENDING_APPROVAL",
    "SpecPhase",
    "SpecStatus",
    "ValidationIssue",
    "ValidationResult",
    "detect_spec_phase",
    "extract_sections",
    "find_section_by_keyword",
    "merge_validation_results",
    "read_spec_doc",
    "validate_spec_structure",
]
from typing import TypedDict

from . import approvals as _approvals, paths as _paths, tasks as _tasks
from .doc_config import DOCUMENT_REGISTRY as _DOCUMENT_REGISTRY
from .text import extract_sections


class SpecPhase:
    """Spec lifecycle phases derived from document existence and approval state."""
    NOT_FOUND = "not-found"
    REQUIREMENTS = "requirements"
    UI_DESIGN = "ui-design"
    DESIGN = "design"
    TASKS = "tasks"
    IMPLEMENTATION = "implementation"
    COMPLETED = "completed"


class SpecStatus:
    """Approval status within the current spec phase."""
    NOT_FOUND = "not-found"
    NOT_STARTED = "not-started"
    PENDING_APPROVAL = "pending-approval"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


PHASE_NOT_FOUND = SpecPhase.NOT_FOUND
PHASE_REQUIREMENTS = SpecPhase.REQUIREMENTS
PHASE_UI_DESIGN = SpecPhase.UI_DESIGN
PHASE_DESIGN = SpecPhase.DESIGN
PHASE_TASKS = SpecPhase.TASKS
PHASE_IMPLEMENTATION = SpecPhase.IMPLEMENTATION
PHASE_COMPLETED = SpecPhase.COMPLETED

STATUS_NOT_FOUND = SpecStatus.NOT_FOUND
STATUS_NOT_STARTED = SpecStatus.NOT_STARTED
STATUS_PENDING_APPROVAL = SpecStatus.PENDING_APPROVAL
STATUS_IN_PROGRESS = SpecStatus.IN_PROGRESS
STATUS_COMPLETED = SpecStatus.COMPLETED


class ValidationIssue(TypedDict):
    severity: str  # "error" | "warning"
    rule: str
    message: str


class ValidationResult(TypedDict):
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]


def merge_validation_results(*results: ValidationResult) -> ValidationResult:
    """Combine multiple validation results into one."""
    return {
        "errors": [e for r in results for e in r["errors"]],
        "warnings": [w for r in results for w in r["warnings"]],
    }


def _derive_doc_names() -> tuple[str, ...]:
    """Derive required doc stem names from DOCUMENT_REGISTRY."""
    doc_registry = _DOCUMENT_REGISTRY["spec"]
    return tuple(doc_registry["doc_stems"][k] for k in doc_registry["doc_keys"])


DOC_NAMES = _derive_doc_names()


def _build_doc_checks() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Derive required/optional heading checks from DOCUMENT_REGISTRY."""
    doc_registry = _DOCUMENT_REGISTRY["spec"]
    headings = doc_registry.get("expected_headings", {})
    stems = doc_registry.get("doc_stems", {})
    optional_keys = set(doc_registry.get("optional_doc_keys", []))
    required: dict[str, list[str]] = {}
    optional: dict[str, list[str]] = {}
    for doc_key in list(doc_registry["doc_keys"]) + list(optional_keys):
        stem = stems.get(doc_key, doc_key.replace("_md", ""))
        h = headings.get(doc_key, [])
        if not h:
            continue
        if doc_key in optional_keys:
            optional[stem] = h
        else:
            required[stem] = h
    return required, optional


DEFAULT_DOC_CHECKS, OPTIONAL_DOC_CHECKS = _build_doc_checks()

_HEADING_ALIASES: dict[str, tuple[str, ...]] = {
    "Purpose": ("Purpose", "Introduction"),
}


def read_spec_doc(root: Path, spec_name: str, doc: str) -> str | None:
    """Read a spec document by name. Returns content or None if missing."""
    fp = _paths.spec_dir(root, spec_name) / f"{doc}.md"
    if fp.is_file():
        return fp.read_text(encoding="utf-8")
    return None


def find_section_by_keyword(sections: dict[str, str], *keywords: str) -> str:
    """Return first section whose heading contains any keyword (case-insensitive)."""
    for heading, body in sections.items():
        h_lower = heading.lower()
        if any(kw.lower() in h_lower for kw in keywords):
            return f"## {heading}\n{body}"
    return ""


def _validate_single_doc(
    spec_path: Path,
    spec_name: str,
    doc: str,
    expected_headings: list[str],
    *,
    required: bool = True,
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    """Validate a single spec document for existence, content, and headings."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    fp = spec_path / f"{doc}.md"

    if not fp.is_file():
        if required:
            errors.append({
                "severity": "error",
                "rule": f"{doc}-exists",
                "message": f"Missing {doc}.md in {spec_name}",
            })
        return errors, warnings

    content = fp.read_text(encoding="utf-8").strip()
    if not content:
        target = errors if required else warnings
        target.append({
            "severity": "error" if required else "warning",
            "rule": f"{doc}-non-empty",
            "message": (f"{doc}.md is empty in {spec_name}" if required
                        else f"{doc}.md exists but is empty in {spec_name}"),
        })
        return errors, warnings

    sections = extract_sections(content)
    for heading in expected_headings:
        aliases = _HEADING_ALIASES.get(heading, (heading,))
        found = any(
            alias.lower() in k.lower()
            for alias in aliases
            for k in sections
        )
        if not found:
            warnings.append({
                "severity": "warning",
                "rule": f"{doc}-heading-{heading.lower()}",
                "message": f"Expected heading containing '{heading}' in {doc}.md",
            })

    return errors, warnings


def validate_spec_structure(
    root: Path, spec_name: str, *, doc_filter: str | None = None,
) -> ValidationResult:
    """Check spec files exist, are non-empty, and have required headings."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    spec_path = _paths.spec_dir(root, spec_name)

    if not spec_path.is_dir():
        errors.append({
            "severity": "error",
            "rule": "spec-dir-exists",
            "message": f"Spec directory not found: {spec_path}",
        })
        return {"errors": errors, "warnings": warnings}

    checks = DEFAULT_DOC_CHECKS
    if doc_filter is not None:
        if doc_filter not in checks:
            raise ValueError(f"Invalid doc_filter '{doc_filter}'. Must be one of {list(checks)}")
        checks = {doc_filter: checks[doc_filter]}

    for doc, expected_headings in checks.items():
        e, w = _validate_single_doc(spec_path, spec_name, doc, expected_headings, required=True)
        errors.extend(e)
        warnings.extend(w)

    if doc_filter is None:
        for doc, expected_headings in OPTIONAL_DOC_CHECKS.items():
            e, w = _validate_single_doc(spec_path, spec_name, doc, expected_headings, required=False)
            errors.extend(e)
            warnings.extend(w)

    return {"errors": errors, "warnings": warnings}


def _check_approval_state(
    spec_path: Path,
    spec_approvals: list[dict],
    approvals_root: Path,
    spec_name: str,
) -> dict[str, bool]:
    """Check approval status for all spec documents.

    Identity check uses canonical absolute path + current-bytes
    sha256. Missing files, legacy approvals (no ``canonicalPath`` /
    ``contentHash``), or drifted content all collapse to ``False``.
    """
    from sdd_core.reference_ledger import hash_file
    doc_registry = _DOCUMENT_REGISTRY["spec"]
    result = {}
    for doc_key in list(doc_registry["doc_keys"]) + list(doc_registry.get("optional_doc_keys", [])):
        filename = doc_registry["doc_files"][doc_key]
        live_path = spec_path / filename
        if not live_path.is_file():
            result[doc_key] = False
            continue
        try:
            canonical = str(live_path.resolve(strict=True))
        except OSError:
            result[doc_key] = False
            continue
        expected = hash_file(live_path)
        if not expected:
            result[doc_key] = False
            continue
        result[doc_key] = _approvals.has_approved_any(
            spec_approvals, canonical, expected, approvals_root, spec_name,
        )
    return result


def _determine_phase(
    spec_path: Path,
    approval_state: dict[str, bool],
    task_progress: dict,
) -> tuple[str, str]:
    """Determine the current phase and status from doc existence and approval state."""
    doc_registry = _DOCUMENT_REGISTRY["spec"]
    doc_files = doc_registry["doc_files"]

    requirements_path = spec_path / doc_files["requirements_md"]
    design_path = spec_path / doc_files["design_md"]
    tasks_path = spec_path / doc_files["tasks_md"]

    ui_design_file = doc_files.get("ui_design_md")
    ui_design_path = spec_path / ui_design_file if ui_design_file else None

    if not requirements_path.exists():
        return PHASE_REQUIREMENTS, STATUS_NOT_STARTED
    if not approval_state.get("requirements_md"):
        return PHASE_REQUIREMENTS, STATUS_PENDING_APPROVAL
    if ui_design_path and ui_design_path.exists() and not approval_state.get("ui_design_md"):
        return PHASE_UI_DESIGN, STATUS_PENDING_APPROVAL
    if not design_path.exists():
        return PHASE_DESIGN, STATUS_NOT_STARTED
    if not approval_state.get("design_md"):
        return PHASE_DESIGN, STATUS_PENDING_APPROVAL
    if not tasks_path.exists():
        return PHASE_TASKS, STATUS_NOT_STARTED
    if not approval_state.get("tasks_md"):
        return PHASE_TASKS, STATUS_PENDING_APPROVAL
    if task_progress["total"] > 0 and task_progress["completed"] == task_progress["total"]:
        return PHASE_COMPLETED, STATUS_COMPLETED
    return PHASE_IMPLEMENTATION, STATUS_IN_PROGRESS


def detect_spec_phase(
    root: Path,
    spec_name: str,
    approvals_list: list[dict] | None = None,
) -> dict:
    """Determine spec phase from R/D/T presence + approval status."""
    approvals_root = _paths.approvals_dir(root)
    if approvals_list is None:
        approvals_list = _approvals.scan_approvals(approvals_root)

    spec_path = _paths.spec_dir(root, spec_name)
    if not spec_path.is_dir():
        return {"phase": PHASE_NOT_FOUND, "status": STATUS_NOT_FOUND}

    spec_approvals = [a for a in approvals_list if a.get("categoryName") == spec_name]
    approval_state = _check_approval_state(
        spec_path, spec_approvals, approvals_root, spec_name,
    )

    doc_files = _DOCUMENT_REGISTRY["spec"]["doc_files"]
    tasks_path = spec_path / doc_files["tasks_md"]

    task_progress = {"total": 0, "completed": 0, "pending": 0, "inProgress": 0}
    if tasks_path.exists():
        parsed = _tasks.parse_tasks(tasks_path.read_text(encoding="utf-8"))
        task_progress = _tasks.calculate_progress(parsed)

    phase, status = _determine_phase(spec_path, approval_state, task_progress)

    return {"phase": phase, "status": status, "taskProgress": task_progress}
