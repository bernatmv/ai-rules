"""Delegation context extraction for cross-repo sub-spec creation."""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from ._workspace_io import find_by_key
from . import specs as _specs
from .workspace_phase import PHASE_STATUS_MAP

__all__ = [
    "DelegationContext",
    "extract_delegation_context",
    "phase_to_status",
]


class DelegationContext(TypedDict, total=False):
    repoId: str
    role: str
    requirements_subset: str
    design_section: str
    api_contracts: str
    depends_on_context: str
    repoType: str


def _find_repo(manifest: dict, repo_id: str) -> dict:
    """Return the repo entry matching *repo_id*, or empty dict."""
    return find_by_key(manifest.get("repos", []), "id", repo_id) or {}


def _extract_requirements_subset(content: str, repo_id: str) -> str:
    if not content:
        return ""
    sections = _specs.extract_sections(content)
    subset = _specs.find_section_by_keyword(sections, repo_id)
    return subset if subset else content


def _extract_design_and_api(
    content: str, repo_id: str, sub_spec: str,
) -> tuple[str, str]:
    if not content:
        return "", ""
    sections = _specs.extract_sections(content)
    search_keys = [repo_id]
    if sub_spec:
        search_keys.append(sub_spec)
    design_section = _specs.find_section_by_keyword(sections, *search_keys)
    api_contracts = _specs.find_section_by_keyword(sections, "api", "contract")
    return design_section, api_contracts


def _extract_dependencies(
    content: str, repo_id: str, sub_spec: str,
) -> str:
    if not content:
        return ""
    from . import tasks
    parsed = tasks.parse_tasks(content)
    deps: list[str] = []
    for t in parsed:
        meta = t.get("metadata", {})
        if meta.get("Repo", "").strip() == repo_id or meta.get("SubSpec", "").strip() == sub_spec:
            depends_on_val = meta.get("DependsOn", "").strip()
            if depends_on_val:
                dep_ids = [d.strip() for d in depends_on_val.split(",")]
                for pt in parsed:
                    if pt["id"] in dep_ids:
                        deps.append(f"Task {pt['id']}: {pt['description']}")
    return "\n".join(deps)


def extract_delegation_context(
    root: Path,
    feature: str,
    repo_id: str,
    *,
    manifest: dict | None = None,
    doc_scope: str | None = None,
) -> DelegationContext:
    """Extract delegation context for a target repo from the coordination spec.

    Pre-reads coordination documents and extracts the design slice for
    *repo_id*.  If *manifest* is provided it is used directly, avoiding a
    redundant disk read.

    When *doc_scope* is set (e.g. ``"requirements"``), only the relevant
    coordination document(s) are read — reducing file I/O during phased
    creation.
    """
    if manifest is None:
        from .workspace_manifest import read_manifest
        manifest = read_manifest(root, feature)

    repo_entry = _find_repo(manifest, repo_id)

    if repo_entry.get("repoType") == "coordinator":
        return {
            "repoId": repo_id,
            "role": repo_entry.get("role", ""),
            "repoType": "coordinator",
            "requirements_subset": "",
            "design_section": "",
            "api_contracts": "",
            "depends_on_context": "",
        }

    role = repo_entry.get("role", "")
    sub_spec = repo_entry.get("subSpec", "")
    coord_spec = manifest.get("feature", feature)

    _read_docs = ("requirements", "design", "tasks")
    if doc_scope is not None:
        _read_docs = (doc_scope,)

    docs = {
        doc: _specs.read_spec_doc(root, coord_spec, doc) or ""
        for doc in _read_docs
    }

    requirements_subset = ""
    if "requirements" in docs:
        requirements_subset = _extract_requirements_subset(docs["requirements"], repo_id)

    design_section = ""
    api_contracts = ""
    if "design" in docs:
        design_section, api_contracts = _extract_design_and_api(
            docs["design"], repo_id, sub_spec,
        )

    depends_on_context = ""
    if "tasks" in docs:
        depends_on_context = _extract_dependencies(docs["tasks"], repo_id, sub_spec)

    return {
        "repoId": repo_id,
        "role": role,
        "repoType": "target",
        "requirements_subset": requirements_subset,
        "design_section": design_section,
        "api_contracts": api_contracts,
        "depends_on_context": depends_on_context,
    }


def phase_to_status(phase: str) -> str:
    """Map spec phase string to tracker status string."""
    return PHASE_STATUS_MAP.get(phase, "pending")
