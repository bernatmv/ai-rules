#!/usr/bin/env python3
"""Synchronise workspace-shared reference docs from the coordinator to every target repo.

Usage:
    .spec-workflow/sdd workspace/sync-skills-pack.py --workspace PATH --target FEATURE [--dry-run]

Reads ``sdd_core/data/workspace_shared_references.yaml`` to determine which
reference files must be byte-identical across all workspace repos.  Copies
the coordinator's version into each target repo that is missing or has a
stale copy.

Emits a single JSON envelope with ``synced_count``, ``unchanged_count``,
``error_count``, and a ``next_action_command`` pointing at the launch retry.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import hashlib
import shutil
from pathlib import Path

from sdd_core import cli, output, paths
from sdd_core.command_templates import build_sync_skills_pack_command
from sdd_core.data_loader import load_yaml
from sdd_core.paths import (
    COMMON_SKILL_NAME,
    COORDINATION_MANIFEST_FILENAME,
    workspace_dir,
)
from sdd_core import workspace_manifest as wm_mod

__sdd_context_needs__ = ("target", "workspace")

__sdd_manifest__ = {
    "summary": "Copy workspace-shared reference docs from coordinator to target repos",
    "flags": ["--workspace", "--target", "--dry-run"],
}

_SHARED_REFS_KEY = "references"
_SHARED_REFS_FILE = "workspace_shared_references.yaml"
_REFERENCES_SUBDIR = "references"


def _sha256(path: Path) -> str:
    try:
        h = hashlib.sha256(path.read_bytes())
        return h.hexdigest()
    except OSError:
        return ""


def _find_skills_root(repo_root: Path) -> Path | None:
    try:
        return paths.find_skills_root(repo_root)
    except FileNotFoundError:
        return None


def _ref_path(skills_root: Path, relative_path: str) -> Path:
    return skills_root / relative_path


def _load_shared_refs() -> list[dict]:
    data = load_yaml(_SHARED_REFS_FILE)
    return [
        r for r in (data.get(_SHARED_REFS_KEY) or [])
        if isinstance(r, dict) and r.get("relative_path")
    ]


def _sync_repo(
    target_root: Path,
    *,
    ref_specs: list[dict],
    coordinator_root: Path,
    coordinator_skills: Path,
    dry_run: bool,
) -> tuple[int, int, int, list[str]]:
    synced = 0
    unchanged = 0
    errors = 0
    details: list[str] = []

    target_skills = _find_skills_root(target_root)
    if target_skills is None:
        try:
            skills_rel = coordinator_skills.relative_to(coordinator_root)
            target_skills = target_root / skills_rel
        except ValueError:
            errors += len(ref_specs)
            details.append(f"skills root not found under {target_root}")
            return synced, unchanged, errors, details

    for ref in ref_specs:
        rel = ref["relative_path"]
        src = _ref_path(coordinator_skills, rel)
        dst = _ref_path(target_skills, rel)

        if not src.is_file():
            errors += 1
            details.append(f"coordinator missing: {rel}")
            continue

        src_sha = _sha256(src)
        dst_sha = _sha256(dst) if dst.exists() else ""

        if src_sha == dst_sha:
            unchanged += 1
            continue

        if dry_run:
            synced += 1
            details.append(f"would sync: {rel}")
            continue

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            synced += 1
        except OSError as exc:
            errors += 1
            details.append(f"copy error for {rel}: {exc}")

    return synced, unchanged, errors, details


def main() -> None:
    parser = cli.workspace_parser(
        "Sync workspace-shared references from coordinator to target repos"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be synced without writing files",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("target", "workspace"))

    root = cli.resolve_workspace_root(args)
    feature = args.feature

    manifest_path = workspace_dir(root, feature) / COORDINATION_MANIFEST_FILENAME
    if not manifest_path.is_file():
        output.error(
            f"No coordination manifest found for feature {feature!r}",
            hint="Run workspace/init-feature.py first",
        )

    try:
        import json
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        output.error(f"Failed to read coordination manifest: {exc}")

    coordinator = wm_mod.get_coordinator(manifest)
    if not coordinator:
        output.error("No coordinator repo declared in coordination manifest")

    coordinator_path = Path(coordinator.get("path", "")).expanduser()
    if not coordinator_path.is_absolute():
        coordinator_path = (root / coordinator_path).resolve()

    coordinator_skills = _find_skills_root(coordinator_path)
    if coordinator_skills is None:
        output.error(
            f"Skills root not found under coordinator at {coordinator_path}",
            hint="Ensure the coordinator repo has a .cursor/skills or .claude/skills directory",
        )

    ref_specs = _load_shared_refs()
    if not ref_specs:
        output.miss(
            {"synced_count": 0, "unchanged_count": 0, "error_count": 0},
            "No workspace-shared references declared",
        )

    target_repos = wm_mod.get_target_repos(manifest)

    total_synced = 0
    total_unchanged = 0
    total_errors = 0
    repo_details: list[dict] = []

    for repo in target_repos:
        repo_path = Path(repo.get("path", "")).expanduser()
        if not repo_path.is_absolute():
            repo_path = (root / repo_path).resolve()

        s, u, e, msgs = _sync_repo(
            repo_path,
            ref_specs=ref_specs,
            coordinator_root=coordinator_path,
            coordinator_skills=coordinator_skills,
            dry_run=args.dry_run,
        )
        total_synced += s
        total_unchanged += u
        total_errors += e
        if msgs or s or e:
            repo_details.append({
                "repo_id": repo.get("id") or repo.get("name") or str(repo_path),
                "synced": s,
                "unchanged": u,
                "errors": e,
                "details": msgs,
            })

    payload: dict = {
        "feature": feature,
        "dry_run": args.dry_run,
        "synced_count": total_synced,
        "unchanged_count": total_unchanged,
        "error_count": total_errors,
        "repos": repo_details,
    }

    if total_synced > 0 or total_unchanged > 0:
        from sdd_core.command_templates import build_workspace_preflight_all_command
        payload["next_action_command"] = build_workspace_preflight_all_command(root)

    verb = "would sync" if args.dry_run else "synced"
    msg = (
        f"Skills pack sync complete: {total_synced} {verb}, "
        f"{total_unchanged} unchanged, {total_errors} error(s)"
    )
    output.success(payload, msg, ctx=ctx)


cli.run_main(main)
