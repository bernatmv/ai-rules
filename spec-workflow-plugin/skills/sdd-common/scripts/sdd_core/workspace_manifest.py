"""Workspace manifest CRUD and validation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict, cast

from ._coerce import coerce_path
from .specs import ValidationIssue, ValidationResult
from ._workspace_io import read_workspace_file, require_workspace_file, write_workspace_file
from .workspace_repo_set import normalise_repo_set

VALID_MANIFEST_STATUSES: frozenset[str] = frozenset({
    "active", "completed", "cancelled",
})

# Single source for repo-id validation. Both bootstrap and mutate paths
# call validate_repo_id so a string accepted by init-feature.py never
# fails downstream in update-manifest.py.
REPO_ID_REGEX: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")

# A bootstrapped workspace whose manifest+tracker are both younger than
# 300 s is treated as "nothing to lose" by ``--force``. 300 s is the
# upper bound on how long a coordinator session can take to type the
# next ``init-feature.py`` invocation; longer windows risk overwriting
# real edits, shorter windows force operators to re-run init.
BOOTSTRAP_PRISTINE_TTL_SECONDS = 300

__all__ = [
    "ManifestRepo",
    "ManifestWorkflow",
    "ManifestData",
    "VALID_MANIFEST_STATUSES",
    "VALID_WORKFLOW_MODES",
    "VALID_REPO_TYPES",
    "MANIFEST_SCHEMA_VERSION",
    "REPO_ID_REGEX",
    "BOOTSTRAP_PRISTINE_TTL_SECONDS",
    "BootstrapFreshness",
    "validate_repo_id",
    "bootstrap_freshness",
    "read_manifest",
    "write_manifest",
    "require_manifest",
    "validate_manifest",
    "get_coordinator",
    "get_target_repos",
    "write_initial_manifest",
    "manifest_repos_match",
]


def validate_repo_id(value: str) -> str:
    """Return ``value`` unchanged when it matches :data:`REPO_ID_REGEX`.

    Raises ``ValueError`` otherwise. Mirrors the regex applied by
    update-manifest.py so a repo-id accepted at bootstrap parse time is
    accepted by every downstream mutator.
    """
    if not isinstance(value, str) or not REPO_ID_REGEX.fullmatch(value):
        raise ValueError(
            f"Invalid repo-id {value!r} — must match {REPO_ID_REGEX.pattern}"
        )
    return value

MANIFEST_SCHEMA_VERSION = "2.0.0"

VALID_WORKFLOW_MODES: frozenset[str] = frozenset({
    "batch-by-doc-type", "vertical",
})

VALID_REPO_TYPES: frozenset[str] = frozenset({
    "coordinator", "target",
})

_VALID_PHASE_NAMES = frozenset({"requirements", "design", "tasks"})


class ManifestRepo(TypedDict, total=False):
    id: str
    name: str
    path: str
    role: str
    repoType: str  # "coordinator" | "target"
    subSpec: str
    skipPhases: list[str]


class ManifestWorkflow(TypedDict, total=False):
    mode: str
    phaseOrder: list[str]


class ManifestData(TypedDict, total=False):
    schemaVersion: str
    feature: str
    repos: list[ManifestRepo]
    workflow: ManifestWorkflow
    createdAt: str
    status: str


def read_manifest(root: "Path | str", feature: str) -> ManifestData:
    """Read coordination-manifest.json from workspace dir."""
    root = coerce_path(root)
    return cast(ManifestData, read_workspace_file(root, feature, "manifest"))


def write_manifest(root: "Path | str", feature: str, data: ManifestData) -> None:
    """Write manifest using atomic_write_json. Creates parent dirs if needed."""
    root = coerce_path(root)
    write_workspace_file(root, feature, "manifest", data)


def require_manifest(root: "Path | str", feature: str, hint: str = "") -> ManifestData:
    """Read manifest or raise ``FileNotFoundError`` if missing."""
    root = coerce_path(root)
    return cast(ManifestData, require_workspace_file(
        root, feature, "manifest",
        hint=hint or "Run the workspace workflow to create a coordination manifest first",
    ))


def get_coordinator(manifest: dict) -> dict:
    """Return the coordinator repo entry, or empty dict."""
    return next(
        (r for r in manifest.get("repos", [])
         if r.get("repoType") == "coordinator"),
        {},
    )


def get_target_repos(manifest: dict) -> list[dict]:
    """Return non-coordinator repos."""
    return [
        r for r in manifest.get("repos", [])
        if r.get("repoType") != "coordinator"
    ]


def _validate_v1_legacy(
    coordinator_legacy: dict,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
) -> None:
    """Validate legacy v1.x top-level ``coordinator`` field.

    v1.x manifests store the coordinator as a separate top-level object
    rather than as a ``repos[]`` entry with ``repoType``.
    """
    coord_required = ("id", "name", "path", "role")
    for field in coord_required:
        if not coordinator_legacy.get(field):
            errors.append({
                "severity": "error",
                "rule": f"manifest-coordinator-{field}",
                "message": f"Coordinator missing '{field}' field",
            })
    coord_path = coordinator_legacy.get("path", "")
    if coord_path and not Path(coord_path).is_dir():
        warnings.append({
            "severity": "warning",
            "rule": "manifest-coordinator-path-exists",
            "message": f"Coordinator path does not exist: {coord_path}",
        })


def validate_manifest(manifest: ManifestData) -> ValidationResult:
    """Validate manifest structure. Returns ValidationResult.

    v2.0.0 schema: all repos (including coordinator) are entries in
    ``repos[]`` with a ``repoType`` discriminator. Exactly one entry
    must have ``repoType == "coordinator"``.
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    if not manifest.get("schemaVersion"):
        errors.append({
            "severity": "error",
            "rule": "manifest-schemaVersion",
            "message": "Manifest missing 'schemaVersion' field",
        })

    if not manifest.get("feature"):
        errors.append({
            "severity": "error",
            "rule": "manifest-feature",
            "message": "Manifest missing 'feature' field",
        })

    status = manifest.get("status", "")
    if status and status not in VALID_MANIFEST_STATUSES:
        errors.append({
            "severity": "error",
            "rule": "manifest-status",
            "message": (
                f"Invalid manifest status '{status}'. "
                f"Valid values: {sorted(VALID_MANIFEST_STATUSES)}"
            ),
        })

    coordinator_legacy = manifest.get("coordinator", {})
    if coordinator_legacy:
        _validate_v1_legacy(coordinator_legacy, errors, warnings)

    repos = manifest.get("repos", [])
    if not repos or len(repos) < 2:
        errors.append({
            "severity": "error",
            "rule": "manifest-repos",
            "message": "Manifest must have at least 2 repos (coordinator + target)",
        })

    feature_name = manifest.get("feature", "")
    coordinator_count = 0
    coord_id_legacy = coordinator_legacy.get("id", "") if coordinator_legacy else ""
    required_fields = ("id", "name", "path", "role", "subSpec")

    for i, repo in enumerate(repos):
        for field in required_fields:
            if not repo.get(field):
                errors.append({
                    "severity": "error",
                    "rule": f"manifest-repo-{field}",
                    "message": f"Repo [{i}] missing '{field}' field",
                })

        repo_type = repo.get("repoType", "")
        if repo_type:
            if repo_type not in VALID_REPO_TYPES:
                errors.append({
                    "severity": "error",
                    "rule": "manifest-repo-repoType",
                    "message": (
                        f"Repo [{i}] repoType '{repo_type}' invalid. "
                        f"Must be one of {sorted(VALID_REPO_TYPES)}"
                    ),
                })
            if repo_type == "coordinator":
                coordinator_count += 1
                if feature_name and repo.get("subSpec") and repo["subSpec"] != feature_name:
                    errors.append({
                        "severity": "error",
                        "rule": "manifest-coordinator-subSpec",
                        "message": (
                            f"Coordinator subSpec '{repo['subSpec']}' must equal "
                            f"feature name '{feature_name}'"
                        ),
                    })
                skip_phases = repo.get("skipPhases", [])
                if skip_phases:
                    errors.append({
                        "severity": "error",
                        "rule": "manifest-coordinator-skipPhases",
                        "message": "Coordinator must not have skipPhases",
                    })

        # v1.x compat: check repo doesn't match legacy coordinator id
        repo_id = repo.get("id", "")
        if coord_id_legacy and repo_id and repo_id == coord_id_legacy and not repo_type:
            errors.append({
                "severity": "error",
                "rule": "manifest-repo-is-coordinator",
                "message": (
                    f"Repo [{i}] id '{repo_id}' matches legacy coordinator id "
                    f"but has no repoType field. In v1.x manifests the coordinator "
                    f"is a separate field — not in repos[]."
                ),
            })

        repo_path = repo.get("path", "")
        if repo_path and not Path(repo_path).is_dir():
            warnings.append({
                "severity": "warning",
                "rule": "manifest-repo-path-exists",
                "message": f"Repo path does not exist: {repo_path}",
            })

        skip_phases = repo.get("skipPhases")
        if skip_phases is not None:
            if not isinstance(skip_phases, list):
                errors.append({
                    "severity": "error",
                    "rule": "manifest-repo-skipPhases-type",
                    "message": f"Repo [{i}] skipPhases must be a list",
                })
            else:
                for sp in skip_phases:
                    if sp not in _VALID_PHASE_NAMES:
                        errors.append({
                            "severity": "error",
                            "rule": "manifest-repo-skipPhases",
                            "message": (
                                f"Repo [{i}] skipPhases value '{sp}' invalid. "
                                f"Must be one of {sorted(_VALID_PHASE_NAMES)}"
                            ),
                        })

    has_repo_types = any(r.get("repoType") for r in repos)
    if has_repo_types and coordinator_count != 1:
        errors.append({
            "severity": "error",
            "rule": "manifest-exactly-one-coordinator",
            "message": (
                f"Expected exactly 1 coordinator in repos[], found {coordinator_count}"
            ),
        })

    workflow = manifest.get("workflow")
    if workflow is not None:
        mode = workflow.get("mode", "")
        if mode and mode not in VALID_WORKFLOW_MODES:
            errors.append({
                "severity": "error",
                "rule": "manifest-workflow-mode",
                "message": (
                    f"Invalid workflow mode '{mode}'. "
                    f"Valid modes: {sorted(VALID_WORKFLOW_MODES)}"
                ),
            })
        phase_order = workflow.get("phaseOrder")
        if phase_order is not None:
            if not isinstance(phase_order, list):
                errors.append({
                    "severity": "error",
                    "rule": "manifest-workflow-phaseOrder-type",
                    "message": "workflow.phaseOrder must be a list",
                })
            else:
                seen = set()
                for po in phase_order:
                    if po not in _VALID_PHASE_NAMES:
                        errors.append({
                            "severity": "error",
                            "rule": "manifest-workflow-phaseOrder",
                            "message": (
                                f"Invalid phaseOrder value '{po}'. "
                                f"Must be one of {sorted(_VALID_PHASE_NAMES)}"
                            ),
                        })
                    if po in seen:
                        errors.append({
                            "severity": "error",
                            "rule": "manifest-workflow-phaseOrder-unique",
                            "message": f"Duplicate phaseOrder value '{po}'",
                        })
                    seen.add(po)

    return {"errors": errors, "warnings": warnings}


_DEFAULT_PHASE_ORDER: tuple[str, ...] = ("requirements", "design", "tasks")
_DEFAULT_WORKFLOW_MODE = "batch-by-doc-type"


def write_initial_manifest(
    workspace_root: "Path | str",
    feature: str,
    repos: list[dict],
    *,
    workflow_mode: str = _DEFAULT_WORKFLOW_MODE,
    phase_order: "tuple[str, ...] | list[str] | None" = None,
) -> Path:
    """Materialise a v2.0.0 manifest with sane defaults.

    Schema knowledge stays here so a future v3.0.0 bump touches one
    factory; the shim re-renders without code change. Returns the
    manifest path written.
    """
    from . import time as sdd_time

    order = list(phase_order) if phase_order else list(_DEFAULT_PHASE_ORDER)
    payload: ManifestData = {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "feature": feature,
        "createdAt": sdd_time.ts_now(),
        "status": "active",
        "workflow": {"mode": workflow_mode, "phaseOrder": order},
        "repos": list(repos),
    }
    write_manifest(workspace_root, feature, payload)
    from .paths import workspace_dir, COORDINATION_MANIFEST_FILENAME
    return workspace_dir(coerce_path(workspace_root), feature) / COORDINATION_MANIFEST_FILENAME


def manifest_repos_match(existing: ManifestData, supplied: list[dict]) -> bool:
    """True when the existing manifest's repo set projection matches *supplied*."""
    return normalise_repo_set(existing.get("repos", []) or [], key_field="id") == \
        normalise_repo_set(supplied, key_field="id")


@dataclass(frozen=True)
class BootstrapFreshness:
    """Outcome of :func:`bootstrap_freshness`.

    ``is_pristine`` is true when the workspace looks "just bootstrapped":
    manifest+tracker exist, both younger than
    :data:`BOOTSTRAP_PRISTINE_TTL_SECONDS`, and no requirements/design/
    tasks doc has been written under any sub-spec.

    ``spec_files_present`` lists the doc paths that disqualified the
    workspace from being pristine — useful for the operator-facing
    advisory body.
    """

    is_pristine: bool
    age_seconds: float
    spec_files_present: tuple[str, ...]


def bootstrap_freshness(
    root: "Path | str",
    feature: str,
    *,
    now: "datetime | None" = None,
) -> BootstrapFreshness:
    """Evaluate whether *feature*'s workspace is a fresh empty bootstrap.

    Pristine means: manifest + tracker both exist on disk, both written
    within the last :data:`BOOTSTRAP_PRISTINE_TTL_SECONDS`, and no
    sub-spec carries any of ``requirements.md``, ``design.md``, or
    ``tasks.md``. The predicate is pure — no side effects — so callers
    can re-evaluate cheaply.
    """
    from .paths import (
        COORDINATION_MANIFEST_FILENAME,
        WORKSPACE_TRACKER_FILENAME,
        workspace_dir,
    )

    root_path = coerce_path(root)
    wd = workspace_dir(root_path, feature)
    manifest_path = wd / COORDINATION_MANIFEST_FILENAME
    tracker_path = wd / WORKSPACE_TRACKER_FILENAME

    if not (manifest_path.is_file() and tracker_path.is_file()):
        return BootstrapFreshness(
            is_pristine=False, age_seconds=float("inf"), spec_files_present=(),
        )

    reference_now = now or datetime.now(tz=timezone.utc)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=timezone.utc)

    def _age(path: Path) -> float:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return (reference_now - mtime).total_seconds()

    manifest_age = _age(manifest_path)
    tracker_age = _age(tracker_path)
    age = max(manifest_age, tracker_age)
    fresh = age <= BOOTSTRAP_PRISTINE_TTL_SECONDS

    spec_present: list[str] = []
    try:
        manifest = read_manifest(root_path, feature)
    except (FileNotFoundError, ValueError):
        manifest = cast(ManifestData, {})
    repos = manifest.get("repos", []) or []
    for repo in repos:
        repo_path = repo.get("path") or ""
        sub_spec = repo.get("subSpec") or ""
        if not (repo_path and sub_spec):
            continue
        repo_root = (root_path / repo_path).resolve()
        spec_dir = repo_root / ".spec-workflow" / "specs" / sub_spec
        for doc in ("requirements.md", "design.md", "tasks.md"):
            candidate = spec_dir / doc
            if candidate.is_file():
                spec_present.append(str(candidate))

    return BootstrapFreshness(
        is_pristine=bool(fresh and not spec_present),
        age_seconds=age,
        spec_files_present=tuple(spec_present),
    )
