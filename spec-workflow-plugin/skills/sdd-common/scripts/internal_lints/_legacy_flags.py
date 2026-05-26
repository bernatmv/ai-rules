"""Single source of truth for legacy-flag constants shared across lints."""
from __future__ import annotations

__all__ = [
    "LEGACY_FLAG_NAMES",
    "CARVE_OUTS",
    "CARVE_OUT_PHRASES",
]

LEGACY_FLAG_NAMES: frozenset[str] = frozenset({
    "--feature",
    "--repo-id",
    "--spec-name",
    "--workspace",
    "--project-path",
    "--target-repo",
    "--target-name",
})

CARVE_OUTS: dict[str, frozenset[str]] = {
    "approval/request.py": frozenset({"--target-name"}),
    "workspace/update-manifest.py": frozenset({"--repo-id"}),
}

CARVE_OUT_PHRASES: tuple[tuple[str, str], ...] = (
    ("--repo-id", "set-repo-role"),
    ("--repo-id", "manifest_repo_id"),
    ("--target-name", "review/pipeline-tick"),
    ("--target-name", "review/pipeline-run"),
    ("--target-name", "validate-review-artifact"),
    ("--target-name", "check-re-review"),
    ("--target-name", "approval/request"),
    ("--target-name", "print-staging-path"),
    ("--target-name", "detect-doc-state"),
)
