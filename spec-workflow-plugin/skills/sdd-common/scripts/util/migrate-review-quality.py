#!/usr/bin/env python3
"""Fold legacy ``review-quality-{phase}.json`` siblings into the canonical artifact.

Usage:
  util/migrate-review-quality.py --spec NAME [--workspace PATH]
  util/migrate-review-quality.py --all       [--workspace PATH]

Idempotent: re-running on a folder whose siblings already migrated is a
no-op (``folded: 0``). Each sibling becomes a ``phase_history[]`` entry
on the canonical artifact, then the sibling is deleted.

Plan-validate-execute seam:
  1. Plan      — list every legacy sibling under the target spec(s).
  2. Validate  — confirm idempotency: zero siblings means no-op.
  3. Execute   — load each sibling, append to phase_history, delete it.

Exits 0 on success or no-op; emits an ``output.success`` envelope listing
the canonical artifacts touched and the siblings folded.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
import re
from pathlib import Path
from typing import Any

from sdd_core import cli, output, paths
from sdd_core import review_quality_schema as schema
from sdd_core.time import ts_now


# Matches "review-quality-<phase>.json" siblings; phase names are spec phases.
_PHASE_FILENAME_RE = re.compile(
    r"^review-quality-(?P<phase>[A-Za-z0-9_-]+)\.json$"
)
# Single source of truth per spec; siblings fold into this artifact's phase_history.
_CANONICAL_FILENAME = "review-quality.json"


def _list_phase_siblings(spec_dir: Path) -> list[Path]:
    if not spec_dir.is_dir():
        return []
    return sorted(
        p for p in spec_dir.iterdir()
        if p.is_file() and _PHASE_FILENAME_RE.match(p.name)
    )


def _list_specs_with_review_quality_artifacts(workspace: Path) -> list[str]:
    specs_root = workspace / paths.WORKFLOW_DIR / paths.SPECS_DIR_NAME
    if not specs_root.is_dir():
        return []
    return sorted(p.name for p in specs_root.iterdir() if p.is_dir())


def _build_phase_entry(
    phase: str, sibling_path: Path, payload: dict[str, Any], now: str,
) -> dict[str, Any]:
    """Build a ``phase_history[]`` entry; existing telemetry survives the fold."""
    approved_at = (
        payload.get("approved_at")
        or payload.get("generated_at")
        or now
    )
    score = (
        payload.get("score_at_approval")
        or payload.get("overall_score")
    )
    entry: dict[str, Any] = {
        "phase": phase,
        "approved_at": approved_at,
        "snapshot_ref": sibling_path.name,
    }
    if score is not None:
        entry["score_at_approval"] = score
    approval_id = payload.get("approval_id") or payload.get("approvalId")
    if approval_id:
        entry["approval_id"] = approval_id
    return entry


def _migrate_spec(
    workspace: Path, spec_name: str, *, dry_run: bool,
) -> dict[str, Any]:
    """Plan-validate-execute the migration for one spec."""
    spec_dir = paths.spec_dir(workspace, spec_name)
    siblings = _list_phase_siblings(spec_dir)
    canonical_path = spec_dir / _CANONICAL_FILENAME

    result: dict[str, Any] = {
        "spec": spec_name,
        "spec_dir": str(spec_dir),
        "canonical": str(canonical_path),
        "folded": 0,
        "siblings": [],
        "deleted": [],
        "skipped_siblings": [],
    }

    if not siblings:
        return result

    canonical = schema.load(canonical_path)

    if not canonical.get("review_type"):
        canonical["review_type"] = "spec"

    now = ts_now()
    for sibling in siblings:
        match = _PHASE_FILENAME_RE.match(sibling.name)
        if not match:
            continue
        phase = match.group("phase")
        try:
            with sibling.open(encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as exc:
            result["skipped_siblings"].append({
                "sibling": sibling.name,
                "reason": "load_failed",
                "detail": str(exc),
            })
            continue
        if not isinstance(payload, dict):
            payload = {}
        entry = _build_phase_entry(phase, sibling, payload, now)
        schema.append_phase_history(canonical, entry)
        result["siblings"].append(sibling.name)

    result["folded"] = len(result["siblings"])

    if dry_run:
        return result

    schema.atomic_write(canonical_path, canonical)
    for sibling_name in result["siblings"]:
        sibling = spec_dir / sibling_name
        try:
            sibling.unlink()
            result["deleted"].append(sibling.name)
        except FileNotFoundError:
            continue

    return result


def main() -> None:
    parser = cli.strict_parser(
        description=(
            "Fold review-quality-{phase}.json siblings into the canonical "
            "review-quality.json artifact (idempotent)."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--spec", dest="spec_name",
        help="Spec name to migrate (e.g. auth-refresh).",
    )
    group.add_argument(
        "--all", dest="all_specs", action="store_true",
        help="Migrate every spec under <workspace>/.spec-workflow/specs/.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Plan + validate; report what would be folded, but do not write.",
    )
    args = parser.parse_args()

    workspace = Path(paths.resolve_project_path(args)).resolve()

    if args.spec_name:
        try:
            paths.validate_name(args.spec_name, kind="spec-name")
        except ValueError as exc:
            output.error(str(exc))
        targets = [args.spec_name]
    else:
        targets = _list_specs_with_review_quality_artifacts(workspace)

    results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    total_folded = 0
    total_skipped_siblings = 0
    for spec_name in targets:
        try:
            result = _migrate_spec(workspace, spec_name, dry_run=args.dry_run)
        except (ValueError, OSError) as exc:
            skipped.append({
                "spec": spec_name,
                "reason": "load_failed",
                "detail": str(exc),
            })
            continue
        results.append(result)
        total_folded += result["folded"]
        total_skipped_siblings += len(result.get("skipped_siblings", []))

    payload: dict[str, Any] = {
        "workspace": str(workspace),
        "specs": results,
        "folded": total_folded,
        "skipped": skipped,
    }
    if args.dry_run:
        payload["dry_run"] = True

    skip_suffix = ""
    if skipped or total_skipped_siblings:
        skip_suffix = (
            f" (skipped {len(skipped)} spec(s), "
            f"{total_skipped_siblings} sibling(s))"
        )

    if total_folded == 0:
        output.success(
            payload,
            (
                f"No legacy siblings found across {len(targets)} spec(s) "
                f"(no-op).{skip_suffix}"
            ),
        )
        return
    output.success(
        payload,
        (
            f"Folded {total_folded} sibling artifact(s) across "
            f"{len(targets)} spec(s).{skip_suffix}"
        ),
    )


if __name__ == "__main__":
    cli.run_main(main)
