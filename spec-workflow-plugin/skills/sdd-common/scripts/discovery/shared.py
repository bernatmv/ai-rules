"""Shared constants and helpers for discovery manifest operations."""
from __future__ import annotations

import json
import shlex
from pathlib import Path

from sdd_core.matchers import WordMatcher
from sdd_core.output import warn as _warn

VALID_PROJECT_STATUSES = {"draft", "in-review", "approved", "archived"}
VALID_ARTIFACT_STATUSES = {"draft", "in-review", "approved"}
VALID_RELATIONSHIPS = {"prd", "ux-flow"}


def build_add_spec_link_command(
    *,
    project: str,
    spec: str,
    relationship: str = "prd",
    project_path: str = ".",
) -> str:
    """Return the exact ``update-manifest.py add-spec-link`` CLI string.

    Single source of truth for the CLI shape. Unit-tested against
    ``discovery/update-manifest.py::build_parser`` so emitters can
    never drift from the real argparse signature — any shape change
    in the CLI must also update this helper or the parity test fails.

    ``relationship`` defaults to ``prd`` (the caller always linking a PRD
    artifact); ``project_path`` defaults to ``.`` since emitters are
    workflow-root relative.
    """
    if relationship not in VALID_RELATIONSHIPS:
        raise ValueError(
            f"Invalid relationship {relationship!r}; "
            f"expected one of {sorted(VALID_RELATIONSHIPS)}"
        )
    return (
        f".spec-workflow/sdd discovery/update-manifest.py "
        f"--name {shlex.quote(project)} "
        f"add-spec-link --spec {shlex.quote(spec)} "
        f"--relationship {relationship}"
    )
REQUIRED_MANIFEST_FIELDS = ("name", "status", "createdAt", "updatedAt")
REQUIRED_ARTIFACT_FIELDS = ("file", "type", "status")
REQUIRED_SPEC_FIELDS = ("name", "relationship")

ARTIFACT_TYPE_MAP: dict[str, str] = {
    "prd": "prd",
    "ux-flow": "ux-flow",
    "ux_flow": "ux-flow",
    "wireframe": "wireframe",
    "research": "research",
    "competitive": "competitive-analysis",
    "comparison": "competitive-analysis",
}
_ARTIFACT_MATCHER = WordMatcher(ARTIFACT_TYPE_MAP.keys(), boundary="none")


def detect_artifact_type(filename: str) -> str:
    """Auto-detect artifact type from filename. Returns 'supplementary' if no match."""
    m = _ARTIFACT_MATCHER.search(filename)
    return ARTIFACT_TYPE_MAP[m.group(1).lower()] if m else "supplementary"


def is_prd_filename(filename: str) -> bool:
    """Check if a filename matches the PRD naming pattern."""
    return detect_artifact_type(filename) == "prd"


def find_prd_files(project_dir: Path) -> list[str]:
    """Return list of PRD filenames in a discovery project folder.

    Checks manifest first (artifacts with type 'prd').
    Falls back to globbing for files matching the PRD pattern.
    """
    manifest_path = project_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text())
            artifacts = data.get("artifacts", [])
            prd_files = []
            for artifact in artifacts:
                if artifact.get("type") == "prd":
                    if "file" not in artifact:
                        _warn(f"PRD artifact missing 'file' key in {manifest_path}")
                        continue
                    prd_files.append(artifact["file"])
            return prd_files
        except json.JSONDecodeError as exc:
            _warn(f"Invalid JSON in manifest {manifest_path}: {exc}; falling back to glob")
    return [f.name for f in project_dir.glob("*.md") if is_prd_filename(f.name)]


def _load_manifest(manifest_path: Path) -> dict | None:
    """Read a manifest.json — returns ``None`` on any read / parse failure.

    Silent failure is intentional (callers iterate across many
    projects) so a single broken manifest doesn't break discovery-wide
    lookups.
    """
    try:
        return json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def find_prd_for_spec(spec_name: str, project_path: Path) -> str | None:
    """Return the project-relative PRD path linked to ``spec_name``.

    Scans every ``.spec-workflow/discovery/*/manifest.json`` and returns
    the first project whose ``specs[].name == spec_name`` has a PRD
    artifact attached. Returns ``None`` when no linked PRD exists —
    callers fall back to the legacy same-name lookup via
    :func:`find_prd_files`.

    Single locator used by launch, detect-context, and slug suggestions;
    composes with :func:`find_prd_files` so the PRD-inside-project
    lookup lives in one place.
    """
    discovery_root = project_path / ".spec-workflow" / "discovery"
    if not discovery_root.is_dir():
        return None
    for project_dir in sorted(discovery_root.iterdir()):
        if not project_dir.is_dir():
            continue
        manifest_path = project_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        data = _load_manifest(manifest_path)
        if not data:
            continue
        linked = False
        for spec in data.get("specs") or []:
            if isinstance(spec, dict) and spec.get("name") == spec_name:
                linked = True
                break
        if not linked:
            continue
        prd_files = find_prd_files(project_dir)
        if not prd_files:
            continue
        rel_path = project_dir.relative_to(project_path) / prd_files[0]
        return str(rel_path)
    return None


def get_discovery_project_names(project_path: Path) -> list[str]:
    """Return sorted discovery project directory names.

    Used by slug suggestions and agent-facing diagnostics. Absent
    ``discovery/`` directory yields an empty list so callers don't have
    to guard for early-lifecycle projects.
    """
    discovery_root = project_path / ".spec-workflow" / "discovery"
    if not discovery_root.is_dir():
        return []
    return sorted(p.name for p in discovery_root.iterdir() if p.is_dir())


def get_discovery_prd_titles(project_path: Path) -> list[str]:
    """Return PRD titles for discovery projects with approved PRDs.

    Reads the first ``# H1`` heading from each linked PRD file. When
    the PRD is missing or lacks an H1 the entry is skipped — absent
    titles don't poison slug suggestions with noise.
    """
    discovery_root = project_path / ".spec-workflow" / "discovery"
    if not discovery_root.is_dir():
        return []
    titles: list[str] = []
    for project_dir in sorted(discovery_root.iterdir()):
        if not project_dir.is_dir():
            continue
        for prd_name in find_prd_files(project_dir):
            prd_path = project_dir / prd_name
            try:
                text = prd_path.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("# "):
                    titles.append(stripped[2:].strip())
                    break
    return titles
