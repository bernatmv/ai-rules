"""Resolve and validate .spec-workflow/ paths."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from typing import Final, Iterable, Iterator

__all__ = [
    "WORKFLOW_DIR",
    "SPECS_DIR_NAME",
    "STANDALONE_DIR_NAME",
    "WORKSPACE_DIR_NAME",
    "TEMPLATE_GLOB",
    "TEMPLATE_SUFFIX",
    "COMMON_SKILL_NAME",
    "STATE_DIR_NAME",
    "COORDINATION_MANIFEST_FILENAME",
    "WORKSPACE_TRACKER_FILENAME",
    "PROMPT_REGISTRY_FILENAME",
    "GATE_SESSION_FILENAME",
    "CATEGORIES",
    "WORKSPACE_ENV_VAR",
    "LEGACY_WORKSPACE_ENV_VAR",
    "common_scripts_dir",
    "common_registry_path",
    "find_workflow_root",
    "require_workflow_root",
    "find_skills_root",
    "require_skills_root",
    "ide_skills_prefixes",
    "is_under",
    "rel_or_abs",
    "spec_dir",
    "spec_name_from_doc_path",
    "approvals_dir",
    "steering_dir",
    "snapshots_dir",
    "archive_dir",
    "templates_dir",
    "impl_logs_dir",
    "validate_path",
    "validate_name",
    "resolve_project_path",
    "state_dir",
    "workspace_state_dir",
    "workflow_state_path",
    "workspace_dir",
    "find_workspace_tracker_root",
    "find_coordinator_root_for_feature",
    "find_workspace_for_target",
    "discovery_dir",
    "discovery_prd_path",
    "doc_dir_path",
    "iter_all_doc_dirs",
    "detect_doc_state_cache_dir",
    "pre_launch_findings_path",
    "template_filename",
    "iter_python_packages",
    "review_quality_artifact_path",
]


WORKSPACE_ENV_VAR: Final[str] = "SDD_WORKSPACE"
LEGACY_WORKSPACE_ENV_VAR: Final[str] = "SDD_PROJECT_PATH"


def resolve_project_path(args: argparse.Namespace) -> str:
    """Resolve the effective workspace path from parsed args.

    Precedence: ``args.project_path`` / ``args.workspace`` →
    ``$SDD_WORKSPACE`` → ``os.getcwd()``. Always returns an absolute
    path string.
    """
    raw = getattr(args, "project_path", None)
    if not raw:
        raw = getattr(args, "workspace", None)
        if raw == ".":
            raw = None
    if raw:
        return os.path.abspath(raw)
    env = os.environ.get(WORKSPACE_ENV_VAR)
    if env:
        return os.path.abspath(env)
    return os.getcwd()

WORKFLOW_DIR = ".spec-workflow"

# Canonical sub-directory names directly under the workflow root —
# tier-specific buckets that the loader composes through. Promoting
# them here lets the loader reach for constants instead of literal
# strings, and the rename surface stays one place.
SPECS_DIR_NAME = "specs"
STANDALONE_DIR_NAME = "standalone"
WORKSPACE_DIR_NAME = "workspace"

TEMPLATE_GLOB = "*-template.md"
TEMPLATE_SUFFIX = "-template.md"

COMMON_SKILL_NAME = "sdd-common"

# Canonical cross-category runtime state directory under the workflow
# root. Single authority — ``harness.json`` and
# ``deferred-tool-preload.json`` both live here; per-doc-target state
# lives under ``<doc_dir>/.sdd-state/`` (see
# :mod:`sdd_core.transient_state`).
STATE_DIR_NAME = ".sdd-state"

# Cross-cutting filename literals — single source for renames + the
# `no_inline_filename_literal` lint. Path-shaped values stay here per
# the convention in `references/script-conventions.md`.
COORDINATION_MANIFEST_FILENAME = "coordination-manifest.json"
WORKSPACE_TRACKER_FILENAME = "workspace-tracker.json"
PROMPT_REGISTRY_FILENAME = "prompt-registry.json"
GATE_SESSION_FILENAME = "gate-session.json"


def state_dir(root: "str | Path") -> Path:
    """Workflow-scoped ``.sdd-state`` directory for cross-cutting state.

    Always rooted at a verified workflow root. Use this when the caller
    already holds the workflow root (e.g. from ``find_workflow_root``);
    callers without the root in hand go through
    :func:`workflow_state_path` instead.
    """
    return Path(root) / WORKFLOW_DIR / STATE_DIR_NAME


def workspace_state_dir(workspace_root: "str | Path") -> Path:
    """Workspace-scoped ``.sdd-state`` directory.

    Same shape as :func:`state_dir` but rooted at the *workspace*
    coordinator rather than a single repo. The reference-ack ledger
    lives here so an ack recorded by any sub-spec satisfies launch
    preconditions for every sibling repo without re-reading the same
    bytes.
    """
    return Path(workspace_root) / WORKFLOW_DIR / STATE_DIR_NAME


def workflow_state_path(filename: str, project_path: str = "") -> str:
    """Absolute path to ``<workflow>/.sdd-state/<filename>``.

    One authority for cross-category state files. Missing workflow
    roots fall back to ``<project>/.spec-workflow/.sdd-state/...`` so
    first-run callers can still compute the intended write target.
    """
    try:
        root = find_workflow_root(project_path or ".")
    except FileNotFoundError:
        base = Path(project_path or os.getcwd()).resolve()
        return str(state_dir(base) / filename)
    return str(state_dir(root) / filename)


def template_filename(doc_type: str) -> str:
    """Build the canonical template filename for a document type."""
    return f"{doc_type}{TEMPLATE_SUFFIX}"


def find_workflow_root(start_dir: str = ".", resolve_symlinks: bool = True) -> Path:
    """Find .spec-workflow/ root, walking up from start_dir.

    When *start_dir* is the default ``"."`` and ``$SDD_WORKSPACE`` is
    set, the env var is used instead of CWD so cross-repo scripts
    resolve paths against the correct project automatically.

    When resolve_symlinks is False, uses os.path.abspath instead of
    Path.resolve() to preserve symlink paths (needed on macOS where
    /var -> /private/var).
    """
    if start_dir == ".":
        start_dir = os.environ.get(WORKSPACE_ENV_VAR) or "."

    current_str = str(Path(start_dir).resolve()) if resolve_symlinks else os.path.abspath(start_dir)
    while True:
        candidate = os.path.join(current_str, WORKFLOW_DIR)
        if os.path.isdir(candidate):
            return Path(current_str)
        parent = os.path.dirname(current_str)
        if parent == current_str:
            raise FileNotFoundError(f"No {WORKFLOW_DIR}/ directory found from {start_dir}")
        current_str = parent


def require_workflow_root(start_dir: str = ".") -> Path:
    """Find .spec-workflow/ root or exit with a user-friendly error."""
    try:
        return find_workflow_root(start_dir)
    except FileNotFoundError:
        from sdd_core import output
        output.error("No .spec-workflow/ directory found", hint="Run workspace/init.py first")
        raise  # unreachable — output.error() exits; raise satisfies NoReturn type check


_IDE_SKILLS_DIRS: tuple[str, ...] = (
    ".cursor/skills",
    ".claude/skills",
)


# Harness adapter name → conventional IDE skills directory. Adding a
# new adapter = one tuple row; ``_probe_order`` and ``find_skills_root``
# never change. Consumers that already hold an adapter pass
# ``harness_name=adapter.name`` so the harness-native tree wins.
_HARNESS_TO_CONVENTIONAL_DIR: dict[str, str] = {
    "cursor": ".cursor/skills",
    "claude-code-standard": ".claude/skills",
    "claude-code-task-variant": ".claude/skills",
}


def ide_skills_prefixes() -> tuple[str, ...]:
    """Return known IDE skills directory relative paths (for tooling)."""
    return _IDE_SKILLS_DIRS


def common_scripts_dir(skills_root: str | Path) -> Path:
    """Canonical scripts directory for the common hub skill."""
    return Path(skills_root) / COMMON_SKILL_NAME / "scripts"


def common_registry_path(skills_root: str | Path) -> Path:
    """Path to skills-registry.json in the common hub skill."""
    return Path(skills_root) / COMMON_SKILL_NAME / "skills-registry.json"


def _probe_order(harness_name: str | None) -> tuple[str, ...]:
    """Return probe order, preferring *harness_name*'s conventional dir."""
    if harness_name and harness_name in _HARNESS_TO_CONVENTIONAL_DIR:
        preferred = _HARNESS_TO_CONVENTIONAL_DIR[harness_name]
        remainder = tuple(d for d in _IDE_SKILLS_DIRS if d != preferred)
        return (preferred,) + remainder
    return _IDE_SKILLS_DIRS


def find_skills_root(
    workspace: str | Path | None = None,
    *,
    harness_name: str | None = None,
) -> Path:
    """Locate the IDE skills directory for the current workspace.

    Probe order:
      1. ``$SDD_SKILLS_ROOT`` environment variable (explicit override).
      2. Conventional directory for *harness_name* when supplied.
      3. Remaining :data:`_IDE_SKILLS_DIRS` in registration order.

    Returns the first existing directory.  Raises ``FileNotFoundError`` when
    no candidate exists.

    Parameters
    ----------
    workspace : str | Path | None
        Workspace root to search from.  When *None*, walks up from cwd
        using the same heuristic as ``find_workflow_root()``.
    harness_name : str | None
        Active adapter name (e.g. ``claude-code-standard``). When
        supplied, the matching conventional directory is tried first so
        pre-resolved paths downstream land on the harness-native tree.
    """
    env = os.environ.get("SDD_SKILLS_ROOT")
    if env:
        p = Path(env)
        if p.is_dir():
            return p

    if workspace is None:
        workspace = find_workflow_root()
    ws = Path(workspace)

    order = _probe_order(harness_name)
    for rel in order:
        candidate = ws / rel
        if candidate.is_dir():
            return candidate

    raise FileNotFoundError(
        f"No skills directory found under {ws} "
        f"(checked: {', '.join(order)})"
    )


def require_skills_root(
    workspace: str | Path | None = None,
    *,
    harness_name: str | None = None,
) -> Path:
    """Find IDE skills directory or raise with a user-friendly error."""
    try:
        return find_skills_root(workspace, harness_name=harness_name)
    except FileNotFoundError:
        from sdd_core import output
        output.error(
            "No skills directory found",
            hint="Expected .cursor/skills/ or .claude/skills/ under workspace root",
        )
        raise  # unreachable — output.error() exits; raise satisfies NoReturn type check


def is_under(path: Path, root: Path) -> bool:
    """True when *path* is contained within *root*."""
    try:
        Path(path).relative_to(Path(root))
        return True
    except ValueError:
        return False


def rel_or_abs(path: Path, root: Path) -> str:
    """Render *path* relative to *root* when possible, else absolute."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(Path(root).resolve()))
    except ValueError:
        return str(p)


def spec_dir(root: Path, spec_name: str) -> Path:
    return root / WORKFLOW_DIR / SPECS_DIR_NAME / spec_name


def spec_name_from_doc_path(path: str | Path) -> str | None:
    """Extract ``<name>`` from a ``.spec-workflow/specs/<name>/<doc>`` path.

    Returns ``None`` when *path* is not inside a ``specs`` directory.
    Uses :class:`pathlib.PurePath.parts` so platform separators and
    repeated slashes are normalised correctly.
    """
    parts = Path(path).parts
    try:
        idx = parts.index(SPECS_DIR_NAME)
    except ValueError:
        return None
    if idx + 1 < len(parts):
        return parts[idx + 1]
    return None


def approvals_dir(root: Path, category_name: str = "") -> Path:
    base = root / WORKFLOW_DIR / "approvals"
    return base / category_name if category_name else base


def steering_dir(root: Path) -> Path:
    return root / WORKFLOW_DIR / "steering"


def snapshots_dir(root: Path, category_name: str, file_name: str) -> Path:
    return root / WORKFLOW_DIR / "approvals" / category_name / ".snapshots" / file_name


def archive_dir(root: Path, spec_name: str) -> Path:
    return root / WORKFLOW_DIR / "archive" / SPECS_DIR_NAME / spec_name


def templates_dir(root: Path, user: bool = False) -> Path:
    subdir = "user-templates" if user else "templates"
    return root / WORKFLOW_DIR / subdir


def impl_logs_dir(root: Path, spec_name: str) -> Path:
    return root / WORKFLOW_DIR / SPECS_DIR_NAME / spec_name / "Implementation Logs"


def validate_path(file_path: str, root: Path) -> Path:
    """Validate: no absolute paths, no '..', contained within *root*.

    Uses :meth:`pathlib.Path.is_relative_to` on strict-resolved paths so
    prefix-match traps like ``/repo-evil/x`` vs ``/repo`` are rejected,
    and symlink escapes are caught at resolution time. Pre-write targets
    (paths that do not exist yet) fall back to non-strict ``resolve()``
    but still pass the containment check against the strict-resolved
    *root*.

    Raises :class:`ValueError` on any violation.
    """
    from pathlib import PurePosixPath
    pp = PurePosixPath(file_path)
    if pp.is_absolute():
        raise ValueError(f"Absolute paths not allowed: {file_path}")
    if ".." in pp.parts:
        raise ValueError(f"Path traversal (..) not allowed: {file_path}")
    root_resolved = Path(root).resolve(strict=True)
    candidate = Path(root) / file_path
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        resolved = candidate.resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ValueError(f"Path escapes project root: {file_path}")
    return resolved


# Pragmatic regex — widened from the initial ``{0,63}`` draft so existing
# spec names (e.g. ``steering.tech``, ``sdd-create-discovery-manifest``)
# still validate on upgrade. The first character must be a letter,
# digit, or underscore; no leading dot, no leading dash, no path
# separators, no control chars. Max length 128 chars.
import re as _re  # noqa: E402 — keep local to avoid polluting the module's public `re`
from sdd_core.security.constants import IDENTIFIER_REGEX as _IDENTIFIER_REGEX  # noqa: E402
_NAME_RE = _re.compile(_IDENTIFIER_REGEX)


def validate_name(name: str, *, kind: str = "identifier") -> str:
    """Validate a user-supplied identifier (spec name, target name, etc.).

    Returns the name unchanged on success. Raises :class:`ValueError`
    with a human-readable explanation on violation. The regex is
    anchored ``^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$`` — letters, digits,
    dots, dashes, underscores; length 1–128.

    Additional rejections:
      * leading ``.`` (hidden paths)
      * containing ``..`` (parent traversal)
      * non-string inputs
    """
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError(
            f"Invalid {kind} {name!r} — must match {_NAME_RE.pattern} "
            f"(letters, digits, dot, dash, underscore; 1-128 chars)"
        )
    if name.startswith(".") or ".." in name:
        raise ValueError(
            f"Invalid {kind} {name!r} — path-like pattern rejected"
        )
    return name


def workspace_dir(root: Path, feature: str = "") -> Path:
    """Return workspace coordination directory path."""
    base = root / WORKFLOW_DIR / WORKSPACE_DIR_NAME
    return base / feature if feature else base


def find_workspace_tracker_root(project_path: "str | Path") -> str:
    """Walk upward from *project_path* to find a workspace tracker.

    Returns the coordinator root path (the directory whose
    ``.spec-workflow/workspace/<feature>/workspace-tracker.json`` is
    present), or an empty string when no tracker is reachable. Single-
    repo projects with no parent workspace get ``""`` so the caller
    falls back to project-only behaviour.
    """
    if not project_path:
        return ""
    current = Path(project_path).resolve()
    visited: set[Path] = set()
    while current not in visited:
        visited.add(current)
        workspace_root = current / WORKFLOW_DIR / WORKSPACE_DIR_NAME
        if workspace_root.is_dir():
            for child in workspace_root.iterdir():
                if (child / WORKSPACE_TRACKER_FILENAME).is_file():
                    return str(current)
        if current.parent == current:
            break
        current = current.parent
    return ""


def find_coordinator_root_for_feature(
    feature: str,
    *,
    search_roots: "Iterable[str | Path]",
) -> str:
    """Return the coordinator root path for *feature*.

    For each entry in *search_roots*, walks up the directory tree
    looking for ``<dir>/.spec-workflow/workspace/<feature>/coordination-manifest.json``.
    The first manifest found whose ``repos`` lists a
    ``repoType=='coordinator'`` entry wins; returns the coordinator's
    ``path`` resolved against the manifest's hosting directory so the
    lookup survives a chdir boundary.

    Returns ``""`` when no reachable manifest names the feature. Pure:
    no chdir, no env reads — search roots are the caller's contract.
    """
    if not feature:
        return ""

    visited: set[Path] = set()
    for raw_root in search_roots:
        if not raw_root:
            continue
        try:
            current = Path(raw_root).resolve()
        except OSError:
            continue
        while True:
            if current in visited:
                break
            visited.add(current)
            manifest_path = (
                current / WORKFLOW_DIR / WORKSPACE_DIR_NAME / feature
                / COORDINATION_MANIFEST_FILENAME
            )
            if manifest_path.is_file():
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    data = None
                if isinstance(data, dict):
                    repos = data.get("repos") or []
                    if isinstance(repos, list):
                        for repo in repos:
                            if not isinstance(repo, dict):
                                continue
                            if repo.get("repoType") != "coordinator":
                                continue
                            repo_path = repo.get("path") or ""
                            if not isinstance(repo_path, str) or not repo_path:
                                continue
                            candidate = Path(repo_path)
                            if not candidate.is_absolute():
                                candidate = (current / candidate).resolve()
                            else:
                                candidate = candidate.resolve()
                            return str(candidate)
            if current.parent == current:
                break
            current = current.parent
    return ""


def _iter_manifest_dirs(
    start: Path, *, visited: set[Path],
) -> Iterator[Path]:
    """Yield every ``.spec-workflow/workspace/<feature>/`` dir reachable upward.

    Walks from *start* to the filesystem root. *visited* deduplicates
    across multiple search roots so a shared ancestor is scanned once.
    """
    current = start
    while True:
        if current in visited:
            return
        visited.add(current)
        workspace_root = current / WORKFLOW_DIR / WORKSPACE_DIR_NAME
        if workspace_root.is_dir():
            for feature_dir in sorted(workspace_root.iterdir()):
                if feature_dir.is_dir():
                    yield feature_dir
        if current.parent == current:
            return
        current = current.parent


def _extract_coordinator_root(manifest: dict, host_dir: Path) -> str:
    """Resolve the coordinator path declared on *manifest*, against *host_dir*.

    Returns the absolute coordinator root as a string, or ``str(host_dir)``
    when the manifest carries no coordinator entry. Relative paths are
    rebased against *host_dir* so the result survives a chdir boundary.
    """
    for repo in (manifest.get("repos") or []):
        if not isinstance(repo, dict):
            continue
        if repo.get("repoType") != "coordinator":
            continue
        repo_path = repo.get("path") or ""
        if not isinstance(repo_path, str) or not repo_path:
            continue
        candidate = Path(repo_path)
        if not candidate.is_absolute():
            candidate = (host_dir / candidate).resolve()
        else:
            candidate = candidate.resolve()
        return str(candidate)
    return str(host_dir)


def _match_target_in_tracker(
    tracker: dict, target_name: str,
) -> "str | None":
    """Return ``repo_id`` of the first sub-spec matching *target_name*, else ``None``."""
    for sub in tracker.get("subSpecs") or []:
        if not isinstance(sub, dict):
            continue
        sub_name = sub.get("subSpecName") or ""
        repo_id = sub.get("repoId") or ""
        if sub_name == target_name or repo_id == target_name:
            return repo_id
    return None


def find_workspace_for_target(
    target_name: str,
    *,
    search_roots: "Iterable[str | Path]",
) -> "tuple[str, str, str] | None":
    """Locate the workspace + coordinator that owns *target_name*.

    Walks every entry in *search_roots* upward, scanning each visited
    directory for a ``coordination-manifest.json`` whose tracker names
    *target_name*. Returns ``(feature, repo_id, coordinator_root)`` on
    success; ``None`` when no reachable manifest matches.
    """
    from . import workspace_tracker as _tracker

    if not target_name:
        return None
    visited: set[Path] = set()
    for raw_root in search_roots:
        if not raw_root:
            continue
        try:
            start = Path(raw_root).resolve()
        except OSError:
            continue
        for feature_dir in _iter_manifest_dirs(start, visited=visited):
            manifest_path = feature_dir / COORDINATION_MANIFEST_FILENAME
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(manifest, dict):
                continue
            host_dir = feature_dir.parent.parent.parent
            coord_root = _extract_coordinator_root(manifest, host_dir)
            try:
                tracker = _tracker.read_tracker_quiet(
                    host_dir, feature_dir.name,
                ).data
            except (OSError, ValueError, KeyError):
                continue
            if not isinstance(tracker, dict):
                continue
            repo_id = _match_target_in_tracker(tracker, target_name)
            if repo_id is not None:
                return (feature_dir.name, repo_id, coord_root)
    return None


def discovery_dir(root: Path, project_name: str = "") -> Path:
    """Return discovery project directory path."""
    base = root / WORKFLOW_DIR / "discovery"
    return base / project_name if project_name else base


def discovery_prd_path(root: Path, project_name: str, prd_name: str = "prd.md") -> Path:
    """Return path to a PRD within a discovery project."""
    return discovery_dir(root, project_name) / prd_name


def pre_launch_findings_path(
    category: str, target_name: str, project_path: str = "",
) -> str:
    """Path to the persisted pre-launch validator findings file.

    Single source of truth for the ``.pre-launch-findings.json`` artifact
    emitted by ``spec/lint-requirements.py`` and consumed by
    ``review --phase pre-launch-check``. Lives alongside the doc itself so
    agents can diff successive runs to measure monotonic progress
    (plan-validate-execute pattern, Skills best-practice § Advanced).
    """
    return os.path.join(
        doc_dir_path(category, target_name, project_path),
        ".pre-launch-findings.json",
    )


def detect_doc_state_cache_dir(
    root: "str | Path", category: str, target_name: str,
) -> Path:
    """Workflow-level cache dir for ``util/detect-doc-state.py`` results.

    Lives under ``<root>/.spec-workflow/.sdd-state/detect-doc-state/<category>/
    <target-name>/`` so cache files never land inside the target doc
    directory (which ``discovery/init-project.py`` and friends treat as
    an ownership signal).
    """
    return (
        Path(root) / WORKFLOW_DIR / STATE_DIR_NAME
        / "detect-doc-state" / category / (target_name or category)
    )


# Single source of truth for category → filesystem-bucket layout.
# ``bucket`` is ``None`` for singleton categories (steering); otherwise
# the workspace carries a parent dir named ``bucket`` with one child
# per target. Adding a new review category is a one-line edit here
# plus one line in ``sdd_core.transient_state.SUPPORTED_CATEGORIES``.
# Unknown categories fall back to the ``spec`` layout to preserve
# historic behaviour of ``doc_dir_path``.
_CATEGORY_BUCKETS: dict[str, str | None] = {
    "steering": None,
    "discovery": "discovery",
    "spec": "specs",
    "workspace": "workspace",
}

CATEGORIES: tuple[str, ...] = tuple(_CATEGORY_BUCKETS.keys())


def review_quality_artifact_path(spec_name: str) -> Path:
    """Canonical location of ``review-quality.json`` for *spec_name*.

    Single source of truth for the artifact path. All readers and writers
    that touch the canonical artifact route through this helper rather
    than composing the path inline.
    """
    return Path(WORKFLOW_DIR) / SPECS_DIR_NAME / spec_name / "review-quality.json"


def doc_dir_path(category: str, target_name: str, project_path: str = "") -> str:
    """Resolve the document directory for a category, optionally under project_path."""
    bucket = _CATEGORY_BUCKETS.get(
        category, _CATEGORY_BUCKETS["spec"],
    )
    if bucket is None:
        rel = f"{WORKFLOW_DIR}/{category}"
    else:
        rel = f"{WORKFLOW_DIR}/{bucket}/{target_name}"
    return os.path.join(project_path, rel) if project_path else rel


def iter_all_doc_dirs(project_path: "str | Path" = "") -> list[Path]:
    """Return every canonical doc-dir that exists under *project_path*.

    Inverse of :func:`doc_dir_path`. Drives pre-flight sweeps that need
    to scan every steering, spec, or discovery doc-target — including
    future categories added to ``_CATEGORY_BUCKETS``. Missing
    directories are skipped silently; the caller owns the "no docs yet"
    semantics.
    """
    root = Path(project_path) if project_path else Path(".")
    sw = root / WORKFLOW_DIR
    dirs: list[Path] = []
    for category, bucket in _CATEGORY_BUCKETS.items():
        if bucket is None:
            singleton = sw / category
            if singleton.is_dir():
                dirs.append(singleton)
            continue
        parent = sw / bucket
        if parent.is_dir():
            dirs.extend(p for p in parent.iterdir() if p.is_dir())
    return dirs


def iter_python_packages(project_root: "str | Path") -> list[str]:
    """Return top-level Python package names available under *project_root*.

    Lookup order (first match wins):

    1. ``pyproject.toml`` — ``[tool.poetry.packages]``,
       ``[tool.setuptools.packages.find]``, and ``[project]``'s
       ``packages`` lists when present. Uses ``tomllib`` from the stdlib
       on Python 3.11+; falls back to a line-oriented scan otherwise so
       the lint remains available on older interpreters.
    2. ``src/*`` directory names (only entries with ``__init__.py`` or
       a ``pyproject.toml`` of their own to skip stray files).
    3. Top-level directories with ``__init__.py``.

    Used by :mod:`internal_lints.import_paths_resolve` to verify that
    dotted module paths (``uvicorn <module>:app``,
    ``python -m <module>``) in steering docs actually resolve against
    the real source tree.
    """
    root = Path(project_root)
    packages: list[str] = []

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib  # py311+
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except Exception:
            data = None
        if isinstance(data, dict):
            # PEP 621 / flit / hatch / setuptools all populate one of
            # these — collect whichever the project is using.
            for pkg in (
                data.get("project", {}).get("packages", [])
                or data.get("tool", {}).get("poetry", {}).get("packages", [])
            ):
                if isinstance(pkg, str):
                    packages.append(pkg)
                elif isinstance(pkg, dict) and pkg.get("include"):
                    packages.append(pkg["include"])
            setup_cfg = (
                data.get("tool", {}).get("setuptools", {})
                .get("packages", {})
            )
            if isinstance(setup_cfg, dict):
                includes = setup_cfg.get("find", {}).get("include") or []
                for entry in includes:
                    if isinstance(entry, str):
                        # ``my_pkg*`` → ``my_pkg`` (first dotted segment).
                        packages.append(entry.split("*", 1)[0].split(".", 1)[0])

    src_dir = root / "src"
    if src_dir.is_dir():
        for entry in sorted(src_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith((".", "_")):
                continue
            if (entry / "__init__.py").is_file() or (entry / "pyproject.toml").is_file():
                packages.append(entry.name)

    if not packages:
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith((".", "_")):
                continue
            if (entry / "__init__.py").is_file():
                packages.append(entry.name)

    # De-dup while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for name in packages:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered
