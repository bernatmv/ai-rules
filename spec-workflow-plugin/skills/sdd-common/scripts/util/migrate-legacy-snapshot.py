#!/usr/bin/env python3
"""Backfill ``canonicalPath`` on legacy approval snapshots.

Usage:
  util/migrate-legacy-snapshot.py --spec NAME --doc BASENAME [--workspace PATH]
  util/migrate-legacy-snapshot.py --all                       [--workspace PATH]

Older snapshots written before the canonical-path identity tuple was
introduced lack the ``canonicalPath`` field. ``has_approved_snapshot``
treats them as legacy and refuses to validate, surfacing a stderr
warning that points at this script. Running the migration backfills
``canonicalPath`` on every snapshot that lacks one, leaving snapshots
that already carry the field untouched.

Idempotent: re-running on a snapshot that already has ``canonicalPath``
is a no-op (``migrated: 0``). Safe under repeated invocation — never
overwrites an existing value with a different one.

Plan-validate-execute seam:
  1. Plan      — list every ``snapshot-NNN.json`` under the target
                 ``.spec-workflow/approvals/<spec>/.snapshots/<basename>/``
                 directory(s) whose body lacks ``canonicalPath``.
  2. Validate  — confirm idempotency: zero candidates means no-op.
  3. Execute   — write ``canonicalPath`` derived from the workflow
                 layout, atomically.

Exits 0 on success or no-op; emits an ``output.success`` envelope with
``migrated: N`` and the list of files touched.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
from pathlib import Path
from typing import Any

from sdd_core import cli, output, paths, snapshots


# Snapshot metadata field — agent-stable, do not rename without migration.
_CANONICAL_PATH_FIELD = "canonicalPath"


def _scan_snapshot_files(
    workflow_root: Path, spec_name: str, basename: str,
) -> tuple[list[tuple[Path, dict]], list[dict[str, Any]]]:
    """Plan the (legacy, skipped) snapshot lists for one (spec, basename) dir.

    Returns a pair ``(legacy_pairs, skipped)`` where ``legacy_pairs`` is
    a list of ``(path, parsed_body)`` for snapshots needing migration
    (missing or empty ``canonicalPath``) and ``skipped`` is a list of
    structured rows for files that failed to parse. Treats both
    ``"canonicalPath"`` missing and ``""`` (empty string) as legacy so
    first-run requests that recorded an empty string still migrate
    cleanly. Caching the parsed body here means ``_migrate_one`` does
    not re-read each file.
    """
    snap_dir = paths.snapshots_dir(workflow_root, spec_name, basename)
    legacy: list[tuple[Path, dict]] = []
    skipped: list[dict[str, Any]] = []
    for snap_file in snapshots.iter_snapshot_files(snap_dir):
        try:
            body = json.loads(snap_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            skipped.append({
                "snapshot": snap_file.name,
                "reason": "load_failed",
                "detail": str(exc),
            })
            continue
        if not isinstance(body, dict):
            skipped.append({
                "snapshot": snap_file.name,
                "reason": "not_a_dict",
                "detail": f"top-level type {type(body).__name__}",
            })
            continue
        if not body.get(_CANONICAL_PATH_FIELD):
            legacy.append((snap_file, body))
    return legacy, skipped


def _list_doc_basenames(workflow_root: Path, spec_name: str) -> list[str]:
    """Return every ``<basename>`` directory under a spec's snapshots root."""
    snap_root = paths.approvals_dir(workflow_root, spec_name) / ".snapshots"
    if not snap_root.is_dir():
        return []
    return sorted(p.name for p in snap_root.iterdir() if p.is_dir())


def _list_specs_with_legacy_snapshots(workflow_root: Path) -> list[str]:
    approvals_root = paths.approvals_dir(workflow_root)
    if not approvals_root.is_dir():
        return []
    out: list[str] = []
    for entry in sorted(approvals_root.iterdir()):
        if not entry.is_dir():
            continue
        if (entry / ".snapshots").is_dir():
            out.append(entry.name)
    return out


def _migrate_one(
    workflow_root: Path, spec_name: str, basename: str, *, dry_run: bool,
) -> dict[str, Any]:
    """Plan-validate-execute for a single (spec, basename) directory.

    Per-snapshot read failures encountered after planning are recorded
    in ``skipped[]`` and the loop continues so a ``--all`` invocation
    surfaces every problem in one pass.
    """
    legacy_pairs, skipped = _scan_snapshot_files(
        workflow_root, spec_name, basename,
    )
    result: dict[str, Any] = {
        "spec": spec_name,
        "doc": basename,
        "snapshots_dir": str(
            paths.snapshots_dir(workflow_root, spec_name, basename)
        ),
        "migrated": 0,
        "files": [],
        "skipped": skipped,
    }
    if not legacy_pairs:
        return result

    canonical_path = snapshots.compute_canonical_path(
        workflow_root, spec_name, basename,
    )
    result["canonical_path"] = canonical_path

    for snap_file, body in legacy_pairs:
        if body.get(_CANONICAL_PATH_FIELD):
            # Defensive — _legacy_snapshot_files already filtered, but a
            # concurrent migrator may have touched this file. Skip silently
            # to preserve idempotency semantics.
            continue
        body[_CANONICAL_PATH_FIELD] = canonical_path
        result["files"].append(snap_file.name)
        if dry_run:
            continue
        try:
            output.atomic_write_json(str(snap_file), body, verify_key="id")
        except (OSError, ValueError) as exc:
            result["files"].pop()
            result["skipped"].append({
                "snapshot": snap_file.name,
                "reason": "write_failed",
                "detail": str(exc),
            })
            continue

    result["migrated"] = len(result["files"])
    return result


def main() -> None:
    parser = cli.strict_parser(
        description=(
            "Backfill canonicalPath on legacy approval snapshots "
            "(idempotent)."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--spec", dest="spec_name",
        help="Spec name (e.g. auth-refresh). Pair with --doc.",
    )
    group.add_argument(
        "--all", dest="all_specs", action="store_true",
        help="Walk every spec under <workspace>/.spec-workflow/approvals/.",
    )
    parser.add_argument(
        "--doc", dest="doc_basename", default=None,
        help="Document basename (e.g. requirements.md).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Plan + validate; report what would be migrated, but do not write.",
    )
    args = parser.parse_args()

    workspace = Path(paths.resolve_project_path(args)).resolve()

    if args.spec_name and not args.doc_basename:
        output.error(
            "--doc is required when --spec is provided",
            hint=(
                "Pass --doc <basename> (e.g. --doc requirements.md), or "
                "use --all to walk every spec."
            ),
        )
    if args.doc_basename and not args.spec_name:
        output.error(
            "--doc requires --spec",
            hint="Pass --spec <name> alongside --doc <basename>.",
        )

    targets: list[tuple[str, str]] = []
    if args.spec_name:
        try:
            paths.validate_name(args.spec_name, kind="spec-name")
        except ValueError as exc:
            output.error(str(exc))
        targets = [(args.spec_name, args.doc_basename)]
    else:
        for spec_name in _list_specs_with_legacy_snapshots(workspace):
            for basename in _list_doc_basenames(workspace, spec_name):
                targets.append((spec_name, basename))

    results: list[dict[str, Any]] = []
    total_migrated = 0
    total_skipped = 0
    for spec_name, basename in targets:
        result = _migrate_one(
            workspace, spec_name, basename, dry_run=args.dry_run,
        )
        results.append(result)
        total_migrated += result["migrated"]
        total_skipped += len(result.get("skipped", []))

    payload: dict[str, Any] = {
        "workspace": str(workspace),
        "targets": results,
        "migrated": total_migrated,
        "skipped": total_skipped,
    }
    if args.dry_run:
        payload["dry_run"] = True

    skip_suffix = f" (skipped {total_skipped})" if total_skipped else ""

    if total_migrated == 0:
        output.success(
            payload,
            (
                f"No legacy snapshots found across {len(targets)} "
                f"target(s) (no-op).{skip_suffix}"
            ),
        )
        return
    output.success(
        payload,
        (
            f"Backfilled canonicalPath on {total_migrated} snapshot(s) "
            f"across {len(targets)} target(s).{skip_suffix}"
        ),
    )


if __name__ == "__main__":
    cli.run_main(main)
