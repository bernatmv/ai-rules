"""Workspace-specific task metadata validation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from .specs import ValidationIssue, ValidationResult

__all__ = [
    "validate_workspace_metadata",
    "ANTIPATTERN_DISPATCH",
    "run_antipattern_lint",
    "lint_cache_path",
    "lint_cache_lookup",
    "lint_cache_store",
]


# Per-doc antipattern lint dispatch — single owner of "which lint runs
# for which doc". Adding a new doc type lands as one row; every caller
# branches on ``doc in ANTIPATTERN_DISPATCH``.
ANTIPATTERN_DISPATCH: dict[str, str] = {
    "requirements": "spec/lint-requirements.py",
    "design": "spec/lint-design.py",
}


def _stderr_to_validation_result(
    doc: str, stderr: str,
) -> ValidationResult:
    """Surface a stderr-only failure as a structured validation error."""
    cleaned = (stderr or "").strip()
    if not cleaned:
        return {"errors": [], "warnings": []}
    errors: list[ValidationIssue] = [{
        "severity": "error",
        "rule": f"{doc}-antipattern-stderr",
        "message": cleaned.splitlines()[0][:500],
    }]
    return {"errors": errors, "warnings": []}


def run_antipattern_lint(
    doc: str,
    spec_path: Path,
    *,
    project_path: "Path | None" = None,
) -> ValidationResult:
    """Subprocess-dispatch the per-doc antipattern lint.

    Maps the lint's ``output.partial(...)`` envelope onto the shared
    :class:`ValidationResult` shape so :func:`specs.merge_validation_results`
    can fold it in. Missing or absent dispatch entries return a clean
    result so the caller never branches on availability.

    A stderr-only failure (empty stdout, non-empty stderr) surfaces as a
    structured error so silent PASS-on-stderr is impossible.
    """
    if doc not in ANTIPATTERN_DISPATCH:
        return {"errors": [], "warnings": []}

    from .subprocess_dispatch import run_dispatched

    script = ANTIPATTERN_DISPATCH[doc]
    args = [str(spec_path)]
    if project_path is not None:
        args.extend(["--workspace", str(project_path)])

    try:
        completed = run_dispatched(script, *args, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError, OSError) as exc:
        return {"errors": [], "warnings": [{
            "severity": "warning",
            "rule": f"antipattern-dispatch-{doc}",
            "message": f"Could not run {script}: {exc}",
        }]}

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if not stdout:
        return _stderr_to_validation_result(doc, stderr)
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        if stderr:
            return _stderr_to_validation_result(doc, stderr)
        return {"errors": [], "warnings": []}

    data = envelope.get("data", {}) if isinstance(envelope, dict) else {}
    issues = data.get("issues", []) or []
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    for issue in issues:
        severity = issue.get("severity", "error")
        record: ValidationIssue = {
            "severity": severity,
            "rule": issue.get("rule", f"{doc}-antipattern"),
            "message": issue.get("message", ""),
        }
        if severity == "error":
            errors.append(record)
        else:
            warnings.append(record)
    return {"errors": errors, "warnings": warnings}


def lint_cache_path(
    project_path: "Path | str", spec_name: str, doc: str,
) -> Path:
    """Path to the per-doc lint cache file under the spec's ``.sdd-state``."""
    from . import workspace_state_loader

    state_dir = workspace_state_loader.resolve_state_dir(
        project_path=str(project_path),
        spec_name=spec_name,
        purpose=workspace_state_loader.PURPOSE_PER_SPEC,
    )
    return state_dir / "lint-cache" / f"{doc}.json"


def _spec_doc_path(project_path: "Path | str", spec_name: str, doc: str) -> Path:
    """Convention path for a spec doc — used to compute the cache key."""
    from .paths import WORKFLOW_DIR

    return (
        Path(project_path) / WORKFLOW_DIR / "specs" / spec_name / f"{doc}.md"
    )


def _cache_signature(doc_path: Path) -> "dict | None":
    """Return ``{mtime, sha256, size}`` for *doc_path*, or ``None`` if missing."""
    if not doc_path.is_file():
        return None
    try:
        stat = doc_path.stat()
        digest = hashlib.sha256(doc_path.read_bytes()).hexdigest()
    except OSError:
        return None
    return {"mtime": stat.st_mtime, "sha256": digest, "size": stat.st_size}


def lint_cache_lookup(
    project_path: "Path | str", spec_name: str, doc: str,
) -> "ValidationResult | None":
    """Return the cached :class:`ValidationResult` if the doc bytes are unchanged.

    Returns ``None`` when the cache is missing, the doc has changed since
    the cache was written, or the cache file is unreadable.
    """
    cache_path = lint_cache_path(project_path, spec_name, doc)
    doc_path = _spec_doc_path(project_path, spec_name, doc)
    sig = _cache_signature(doc_path)
    if sig is None or not cache_path.is_file():
        return None
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    cached_sig = payload.get("signature") or {}
    if cached_sig.get("sha256") != sig["sha256"]:
        return None
    result = payload.get("result") or {}
    if not isinstance(result, dict):
        return None
    return {
        "errors": list(result.get("errors") or []),
        "warnings": list(result.get("warnings") or []),
    }


def lint_cache_store(
    project_path: "Path | str",
    spec_name: str,
    doc: str,
    result: ValidationResult,
) -> None:
    """Persist *result* keyed by the doc's current sha256."""
    cache_path = lint_cache_path(project_path, spec_name, doc)
    doc_path = _spec_doc_path(project_path, spec_name, doc)
    sig = _cache_signature(doc_path)
    if sig is None:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "signature": sig,
        "result": {
            "errors": list(result.get("errors") or []),
            "warnings": list(result.get("warnings") or []),
        },
    }
    tmp = cache_path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True)
    os.replace(tmp, cache_path)


def validate_workspace_metadata(tasks_list: list[dict]) -> ValidationResult:
    """Validate workspace-specific metadata fields on tasks.

    Returns ValidationResult matching the canonical format from
    task_validation.validate().
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for task in tasks_list:
        meta = task.get("metadata", {})
        task_id = task.get("id", "?")

        repo = meta.get("Repo")
        if repo is not None:
            if not repo.strip():
                errors.append({
                    "severity": "error",
                    "rule": "workspace-repo-non-empty",
                    "message": f"Task {task_id}: _Repo_ metadata is empty",
                })

        sub_spec = meta.get("SubSpec")
        if sub_spec is not None:
            val = sub_spec.strip()
            if not val:
                errors.append({
                    "severity": "error",
                    "rule": "workspace-subspecs-non-empty",
                    "message": f"Task {task_id}: _SubSpec_ metadata is empty",
                })
            elif not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", val):
                errors.append({
                    "severity": "error",
                    "rule": "workspace-subspecs-kebab",
                    "message": f"Task {task_id}: _SubSpec_ '{val}' is not valid kebab-case",
                })

        depends_on = meta.get("DependsOn")
        if depends_on is not None:
            val = depends_on.strip()
            if val:
                all_ids = {t.get("id") for t in tasks_list}
                for dep_id in (d.strip() for d in val.split(",")):
                    if dep_id and dep_id not in all_ids:
                        errors.append({
                            "severity": "error",
                            "rule": "workspace-depends-on-valid",
                            "message": f"Task {task_id}: _DependsOn_ references unknown task '{dep_id}'",
                        })

    return {"errors": errors, "warnings": warnings}
