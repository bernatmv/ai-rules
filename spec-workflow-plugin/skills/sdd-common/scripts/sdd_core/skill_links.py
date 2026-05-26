"""Reusable link-checking logic for SDD skill .md files.

Public facade that re-exports from sub-modules and provides the
high-level scanning / validation functions.

Sub-modules:
  skill_links_parse   — regex patterns, reference extraction, prose iteration
  skill_links_resolve — path resolution, fix logic, prefix registry
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .paths import (
    COMMON_SKILL_NAME,
    common_scripts_dir,
    common_registry_path,
)


# Mirrors ``scripts/lib/sdd_utils.py::HASH_EXCLUDE_*`` exactly so the
# in-tree drift check produces a hash byte-equal to the registry
# generator's. Drift in either constant propagates here on the next
# read; if the lists ever diverge the registry check would surface
# as a false positive — a useful regression signal in itself.
_HASH_EXCLUDE_NAMES = frozenset(
    {"manifest.json", "skills-registry.json", "package.json"},
)
_HASH_EXCLUDE_SUFFIXES = frozenset({".pyc"})
_HASH_EXCLUDE_DIR_PARTS = frozenset({
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    ".tox",
    ".coverage",
    "node_modules",
    ".DS_Store",
})


def hash_skill_dir(directory: "str | Path") -> str:
    """Return the deterministic SHA-256 of every file under *directory*.

    Mirrors ``scripts/lib/sdd_utils.hash_dir_contents`` so the workspace
    drift check (W4) produces an identical digest to the registry
    generator. Empty / missing directories return ``""``.
    """
    root = Path(directory)
    if not root.is_dir():
        return ""

    excluded_parts = _HASH_EXCLUDE_DIR_PARTS

    def _included(path: Path) -> bool:
        if path.name in _HASH_EXCLUDE_NAMES:
            return False
        if any(path.name.endswith(s) for s in _HASH_EXCLUDE_SUFFIXES):
            return False
        rel_parts = path.relative_to(root).parts
        return not any(part in excluded_parts for part in rel_parts)

    files = sorted(
        f for f in root.rglob("*") if f.is_file() and _included(f)
    )
    if not files:
        return ""
    h = hashlib.sha256()
    for f in files:
        rel = str(f.relative_to(root))
        try:
            file_hash = hashlib.sha256(f.read_bytes()).hexdigest()
        except OSError:
            continue
        h.update(f"{file_hash}  {rel}\n".encode())
    return h.hexdigest()

from .skill_links_parse import (  # noqa: F401
    _MD_LINK_RE,
    _BACKTICK_PATH_RE,
    _TABLE_PATH_RE,
    _SCRIPT_INVOCATION_RE,
    _build_path_alternatives,
    _iter_prose_lines,
    _is_skippable,
    _extract_refs,
    _parse_prefix_table,
)
from .skill_links_resolve import (  # noqa: F401
    _FIX_CROSS_SKILL_RELATIVE_RE,
    _FIX_REPO_ABS_RE,
    _NOVERIFY_RE,
    _CROSS_SKILL_RELATIVE_RE,
    _get_file_index,
    _suggest_fix,
    _resolve_path,
    fix_file,
    _RESOLVE_REGISTRY,
    _register_prefix,
    _implemented_prefixes,
)

__all__ = [
    "scan_file",
    "fix_file",
    "check_script_invocations",
    "check_manifest",
    "check_registry",
    "check_consumer_refs",
    "check_conventions_consistency",
    "discover_phantom_candidates",
    "hash_skill_dir",
    "_get_file_index",
]
_PHANTOM_FLAT_NAMES_BASELINE = {
    "check-template-compliance.py",
}


def discover_phantom_candidates(scripts_root: str) -> set[str]:
    """Build phantom name set by scanning grouped scripts on disk.

    Any .py file in a subdirectory (e.g., spec/check-status.py) that might
    be referenced as a bare name (check-status.py) is a phantom candidate.
    """
    candidates: set[str] = set()
    if not os.path.isdir(scripts_root):
        return candidates
    for dirpath, _, filenames in os.walk(scripts_root):
        if os.path.normpath(dirpath) == os.path.normpath(scripts_root):
            continue
        for fn in filenames:
            if fn.endswith(".py") and fn != "__init__.py":
                candidates.add(fn)
    return candidates


def _get_phantom_names(skills_root: str | None = None) -> set[str]:
    """Return the union of baseline phantom names and disk-discovered candidates."""
    names = set(_PHANTOM_FLAT_NAMES_BASELINE)
    if skills_root:
        scripts_root = str(common_scripts_dir(skills_root))
        names |= discover_phantom_candidates(scripts_root)
    return names


def _make_issue(rel_file, lineno, kind, raw_path, category, resolved,
                exists, fix, severity, **extra):
    """Build a standardised issue dict."""
    issue = {
        "file": rel_file,
        "line": lineno,
        "kind": kind,
        "ref": raw_path,
        "category": category,
        "resolved": resolved,
        "exists": exists,
        "fix": fix,
        "severity": severity,
    }
    issue.update(extra)
    return issue


def _load_registry(skills_root):
    """Load skills-registry.json, returning (data | None, path)."""
    reg_path = str(common_registry_path(skills_root))
    if not os.path.exists(reg_path):
        return None, reg_path
    with open(reg_path) as f:
        return json.load(f), reg_path


def scan_file(filepath, skills_root, workspace_root, *, check_phantoms=False, file_index=None):
    """Scan a .md file for reference issues.

    Returns (issues, consumer_refs) where issues is a list of issue dicts and
    consumer_refs is a list of (defining_file, raw_path) tuples for @consumer/ paths.

    Parameters
    ----------
    file_index : dict[str, list[str]] | None
        Optional pre-built basename index from _get_file_index() to avoid
        repeated os.walk calls in _suggest_fix.
    """
    issues = []
    consumer_refs: list[tuple[str, str]] = []
    file_dir = os.path.dirname(os.path.abspath(filepath))
    rel_file = os.path.relpath(filepath, workspace_root)

    phantom_re = None
    if check_phantoms:
        phantom_names = _get_phantom_names(skills_root)
        if phantom_names:
            phantom_re = re.compile(
                r"`(" + "|".join(re.escape(n) for n in sorted(phantom_names)) + r")"
                r"(?:\s[^`]*)?" r"`"
            )

    if file_index is None:
        file_index = _get_file_index(skills_root)

    try:
        prose_lines = list(_iter_prose_lines(filepath))
    except (IOError, OSError):
        return issues, consumer_refs

    for lineno, line in prose_lines:
        for raw_path, kind in _extract_refs(line):
            resolved, category, fix = _resolve_path(
                raw_path, file_dir, skills_root, workspace_root
            )
            if resolved is None:
                if category == "consumer":
                    consumer_refs.append((rel_file, raw_path))
                continue

            if category in ("cross-skill-relative", "repo-absolute"):
                exists = os.path.exists(resolved)
                issues.append(_make_issue(
                    rel_file, lineno, kind, raw_path, category,
                    os.path.relpath(resolved, workspace_root),
                    exists, fix,
                    "non-portable" if exists else "broken",
                ))
            elif not os.path.exists(resolved):
                hint = None
                if category == "skills-prefix":
                    rel = raw_path[len("$SKILLS/"):]
                    hint = _suggest_fix(rel, skills_root, file_index)
                issues.append(_make_issue(
                    rel_file, lineno, kind, raw_path, category,
                    os.path.relpath(resolved, workspace_root),
                    False, fix or hint, "broken",
                    **({"hint": hint} if hint else {}),
                ))

        if phantom_re:
            for m in phantom_re.finditer(line):
                phantom = m.group(1)
                issues.append(_make_issue(
                    rel_file, lineno, "phantom-bare", phantom,
                    "phantom", "", False, None, "phantom",
                ))

    return issues, consumer_refs


def check_script_invocations(skills_root, workspace_root, md_files):
    """Verify that script invocations in .md files resolve to actual files.

    Parameters
    ----------
    md_files : list[str]
        Pre-collected list of markdown file paths to check.
    """
    scripts_root = str(common_scripts_dir(skills_root))
    issues = []
    for md_file in md_files:
        rel_file = os.path.relpath(md_file, workspace_root)
        try:
            prose_lines = list(_iter_prose_lines(md_file))
        except (IOError, OSError):
            continue
        for lineno, line in prose_lines:
            for m in _SCRIPT_INVOCATION_RE.finditer(line):
                script_rel = m.group(1)
                if "{" in script_rel or script_rel.startswith("--"):
                    continue
                script_path = os.path.join(scripts_root, script_rel)
                if not os.path.exists(script_path) and not script_rel.endswith(".py"):
                    script_path = script_path + ".py"
                if not os.path.exists(script_path):
                    issues.append({
                        "file": rel_file,
                        "line": lineno,
                        "ref": f"$SKILLS/{COMMON_SKILL_NAME}/scripts/{script_rel}",
                        "resolved": os.path.relpath(script_path, workspace_root),
                        "severity": "broken-invocation",
                    })
    return issues


def check_manifest(skills_root):
    """Verify manifest.json entries resolve to actual files on disk."""
    scripts_root = str(common_scripts_dir(skills_root))
    manifest_path = os.path.join(scripts_root, "manifest.json")
    if not os.path.exists(manifest_path):
        return [{"severity": "warning", "message": "manifest.json not found"}]
    with open(manifest_path) as f:
        manifest = json.load(f)
    issues = []
    for entry in manifest.get("scripts", []):
        full_path = os.path.join(scripts_root, entry)
        if not os.path.exists(full_path):
            issues.append(
                {
                    "severity": "manifest-missing",
                    "message": f"manifest entry '{entry}' not found on disk",
                }
            )
    return issues


def check_registry(skills_root, workspace_root):
    """Cross-check skills-registry.json entries against disk."""
    registry, reg_path = _load_registry(skills_root)
    if registry is None:
        return [{"severity": "warning", "message": "skills-registry.json not found"}]

    issues = []
    for skill in registry.get("skills", []):
        skill_name = skill["name"]
        skill_dir = os.path.join(skills_root, skill_name)
        for file_rel in skill.get("files", []):
            file_path = os.path.join(skill_dir, file_rel)
            if not os.path.exists(file_path):
                issues.append(
                    {
                        "severity": "registry-missing",
                        "message": f"{skill_name}/{file_rel} in registry but not on disk",
                    }
                )
        for dep_path in skill.get("externalDependencies", []):
            if dep_path.startswith("$SKILLS/"):
                resolved = os.path.join(skills_root, dep_path[len("$SKILLS/"):])
                if not os.path.exists(resolved):
                    issues.append(
                        {
                            "severity": "registry-broken-dep",
                            "message": f"{skill_name} depends on {dep_path} (not found)",
                        }
                    )
    return issues


def check_consumer_refs(skills_root, consumer_refs):
    """Verify @consumer/ references resolve in at least one consuming skill.

    Parameters
    ----------
    skills_root : str
        Path to the IDE skills directory.
    consumer_refs : list[tuple[str, str]]
        List of (defining_file, raw_path) tuples collected during scan_file.
    """
    if not consumer_refs:
        return []
    registry, _ = _load_registry(skills_root)
    if registry is None:
        return []

    issues = []
    for defining_file, raw_path in consumer_refs:
        rel = raw_path[len("@consumer/"):]
        found_in_any = False
        for skill in registry.get("skills", []):
            skill_dir = os.path.join(skills_root, skill["name"])
            if os.path.exists(os.path.join(skill_dir, rel)):
                found_in_any = True
                break
        if not found_in_any:
            issues.append({
                "severity": "consumer-unresolved",
                "message": f"@consumer/{rel} in {defining_file} not found in any skill",
            })
    return issues


def check_conventions_consistency(skills_root: str) -> list[dict]:
    """Compare documented prefixes against implemented resolution categories."""
    conventions_path = os.path.join(
        skills_root, COMMON_SKILL_NAME, "references", "path-conventions.md"
    )
    if not os.path.exists(conventions_path):
        return [{"severity": "warning", "message": "path-conventions.md not found"}]

    documented = _parse_prefix_table(conventions_path)
    implemented = _implemented_prefixes()
    issues = []

    def _is_covered(prefix: str, known: set[str]) -> bool:
        if prefix in known:
            return True
        reg = _RESOLVE_REGISTRY.get(prefix)
        if reg and reg["equivalents"] & known:
            return True
        for k in known:
            k_reg = _RESOLVE_REGISTRY.get(k)
            if k_reg and prefix in k_reg["equivalents"]:
                return True
        return False

    for prefix in documented:
        if prefix.startswith("~~"):
            continue
        if not _is_covered(prefix, implemented):
            issues.append({
                "severity": "convention-drift",
                "message": f"Prefix {prefix!r} documented but not implemented in _resolve_path",
            })
    for pfx in implemented:
        reg = _RESOLVE_REGISTRY.get(pfx, {})
        if reg.get("doc_skip"):
            continue
        if not _is_covered(pfx, documented):
            issues.append({
                "severity": "convention-drift",
                "message": f"Category {pfx!r} implemented but not documented in path-conventions.md",
            })
    return issues
