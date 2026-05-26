#!/usr/bin/env python3
"""Check spec status, phase detection, and task progress.

Usage: .spec-workflow/sdd spec/check-status.py --target NAME | --all | --type steering
"""

from __future__ import annotations
import _bootstrap  # noqa: F401

from pathlib import Path

from sdd_core import git, paths, approvals, specs, output, cli, handoffs, tasks
from sdd_core.tasks import COMPLETED_STATUS
from sdd_core.doc_config import DOCUMENT_REGISTRY
from sdd_core.doc_validation import PHASE_NOT_FOUND, STATUS_COMPLETED
from sdd_core.reference_ledger import hash_file
from sdd_core.security.audit import audit_sink
from sdd_core.time import ts_from_epoch
from sdd_core.paths import WORKFLOW_DIR

# Mirrors workflow-graph.json `sdd-create-spec.context_needs`.
__sdd_context_needs__ = ("target", "workspace")


def _approval_identity(path: "Path") -> "tuple[str, str] | None":
    """Resolve *path* to ``(canonical_absolute_path, sha256_hex)``.

    Returns ``None`` when the file is absent or unreadable so callers
    collapse to "not approved" rather than raise.
    """
    if not path.is_file():
        return None
    try:
        canonical = str(path.resolve(strict=True))
    except OSError:
        return None
    digest = hash_file(path)
    if not digest:
        return None
    return canonical, digest


def _file_modified(fp: Path) -> str | None:
    if fp.exists():
        return ts_from_epoch(fp.stat().st_mtime)
    return None


def _spec_phase_docs() -> list[tuple[str, str, bool]]:
    """Derive phase-docs list from DOCUMENT_REGISTRY (single source of truth)."""
    reg = DOCUMENT_REGISTRY["spec"]
    optional = set(reg.get("optional_doc_keys", []))
    result = []
    for key in list(reg["doc_keys"]) + list(optional):
        stem = reg["doc_stems"][key]
        filename = reg["doc_files"][key]
        result.append((stem, filename, key in optional))
    return result


_SPEC_PHASE_DOCS = _spec_phase_docs()


def _audit_log_path(root: Path) -> "Path | None":
    """Return the canonical approval audit log path under *root*, if any.

    Reads through the audit-sink seam so a non-default sink (e.g.
    syslog mirror) reports the actual flat-file mirror without
    hard-coding the filename here.
    """
    try:
        recorded = audit_sink().path(channel="approval", project_path=str(root))
    except (FileNotFoundError, OSError, ValueError):
        return None
    if not recorded:
        return None
    candidate = Path(recorded)
    return candidate if candidate.is_file() else None


def _build_phases_array(
    sd, spec_approvals, approvals_root, spec_name,
    *, include_audit_log: bool = False,
    audit_log_path: "Path | None" = None,
) -> list[dict]:
    """Build the per-document phases array for presentation.

    Derives from _SPEC_PHASE_DOCS so adding a new optional doc type
    only requires appending an entry to the list.

    When *include_audit_log* is set, the per-doc approval flag is the
    union of :func:`approvals.has_approved_any` (snapshot/active layer)
    and :func:`approvals.has_approved_audit` (audit log) so a phase
    that cleared via an approve transition without a current snapshot
    still reports ``approved: True``.
    """
    phases = []
    for name, filename, optional in _SPEC_PHASE_DOCS:
        fp = sd / filename
        if optional and not fp.exists():
            continue
        identity = _approval_identity(fp)
        if identity is None:
            approved = False
        else:
            canonical, digest = identity
            approved = approvals.has_approved_any(
                spec_approvals, canonical, digest, approvals_root, spec_name,
            )
        if (
            not approved
            and include_audit_log
            and audit_log_path is not None
        ):
            approved = approvals.has_approved_audit(
                audit_log_path, filename, category_name=spec_name,
            )
        phases.append({
            "name": name,
            "exists": fp.exists(),
            "approved": approved,
            "lastModified": _file_modified(fp),
        })
    return phases


def _create_flow_phase_pending_advisory(
    phases: list[dict],
) -> "dict | None":
    """Return a structured advisory when a later phase is approved but a
    prior one is still pending.

    Per-doc create-mode advancement check: agents flag a non-monotonic
    approval order so the user notices that ``design.md`` was approved
    while ``requirements.md`` is still pending. The phase order follows
    ``_SPEC_PHASE_DOCS`` which is itself derived from
    ``DOCUMENT_REGISTRY`` (single source of truth).
    """
    pending: list[str] = []
    out_of_order: list[str] = []
    seen_pending = False
    for entry in phases:
        if not entry.get("exists"):
            continue
        name = entry.get("name") or ""
        if not entry.get("approved"):
            seen_pending = True
            pending.append(name)
            continue
        if seen_pending:
            out_of_order.append(name)
    if not out_of_order:
        return None
    return {
        "name": "create_flow_phase_still_pending",
        "detail": (
            "Approved later phase(s) while earlier ones remain pending: "
            f"approved={out_of_order}, pending={pending}."
        ),
        "pending_phases": pending,
        "approved_after_pending": out_of_order,
    }


def check_single_spec(
    root, spec_name, approvals_list=None,
    *, include_audit_log: bool = False,
) -> dict | None:
    sd = paths.spec_dir(root, spec_name)
    if not sd.is_dir():
        return None

    approvals_root = paths.approvals_dir(root)
    if approvals_list is None:
        approvals_list = approvals.scan_approvals(approvals_root)

    result = specs.detect_spec_phase(root, spec_name, approvals_list=approvals_list)
    if result["phase"] == PHASE_NOT_FOUND:
        return None

    spec_approvals = [a for a in approvals_list if a.get("categoryName") == spec_name]
    audit_log_path = _audit_log_path(root) if include_audit_log else None
    phases = _build_phases_array(
        sd, spec_approvals, approvals_root, spec_name,
        include_audit_log=include_audit_log,
        audit_log_path=audit_log_path,
    )

    payload: dict = {
        "specName": spec_name,
        "currentPhase": result["phase"],
        "overallStatus": result["status"],
        "phases": phases,
        "taskProgress": result["taskProgress"],
    }
    advisory = _create_flow_phase_pending_advisory(phases)
    if advisory is not None:
        payload["create_flow_phase_still_pending"] = advisory
    return payload


def check_all_specs(root, *, include_audit_log: bool = False) -> list[dict]:
    specs_root = root / WORKFLOW_DIR / "specs"
    if not specs_root.is_dir():
        return []
    approvals_root = paths.approvals_dir(root)
    all_approvals = approvals.scan_approvals(approvals_root)
    results = []
    for entry in sorted(specs_root.iterdir()):
        if entry.is_dir():
            info = check_single_spec(
                root, entry.name, approvals_list=all_approvals,
                include_audit_log=include_audit_log,
            )
            if info:
                results.append(info)
    return results


def _steering_docs() -> list[tuple[str, str]]:
    """Derive steering doc list from DOCUMENT_REGISTRY (single source of truth)."""
    reg = DOCUMENT_REGISTRY["steering"]
    return [(reg["doc_stems"][k], reg["doc_files"][k]) for k in reg["doc_keys"]]


_STEERING_DOCS = _steering_docs()


def _verify_logs(root, spec_name, info) -> dict:
    """Cross-check [x] markers against implementation log files."""
    sd = paths.spec_dir(root, spec_name)
    tasks_file = sd / "tasks.md"
    if not tasks_file.exists():
        return info

    parsed = tasks.parse_tasks(tasks_file.read_text())
    completed_ids = [t["id"] for t in parsed if t.get("status") == COMPLETED_STATUS]

    if not completed_ids:
        info["logVerification"] = {
            "verified": True,
            "completedTasks": 0,
            "tasksWithLogs": 0,
            "missingLogs": [],
        }
        return info

    logs_dir = paths.impl_logs_dir(root, spec_name)

    tasks_with_logs = []
    missing_logs = []
    for tid in completed_ids:
        matches = list(logs_dir.glob(f"task-{tid}_*.md")) if logs_dir.exists() else []
        if matches:
            tasks_with_logs.append(tid)
        else:
            missing_logs.append(tid)

    verified = len(missing_logs) == 0
    info["logVerification"] = {
        "verified": verified,
        "completedTasks": len(completed_ids),
        "tasksWithLogs": len(tasks_with_logs),
        "missingLogs": missing_logs,
    }
    if not verified and info.get("overallStatus") == STATUS_COMPLETED:
        info["overallStatus"] = "completed-unverified"

    try:
        # Deferred: impl_session is optional; not available in all invocation contexts
        from impl.impl_session import read_session, detect_stale_session
    except ImportError:
        info["logVerification"]["sessionState"] = {"exists": False}
    else:
        try:
            session = read_session(spec_name, str(root))
            stale = detect_stale_session(session)
            info["logVerification"]["sessionState"] = {
                "exists": session.get("spec_name") is not None,
                "execution_mode": session.get("execution_mode"),
                "completed_tasks": len(session.get("completed_tasks") or []),
                "current_task": (session.get("current_task") or {}).get("id"),
                "stale": stale["is_stale"],
            }
        except (ValueError, KeyError, TypeError) as exc:
            info["logVerification"]["sessionState"] = {
                "exists": False,
                "error": str(exc),
            }

    return info


def check_steering(root) -> dict:
    st = paths.steering_dir(root)
    approvals_root = paths.approvals_dir(root)
    all_approvals = approvals.scan_approvals(approvals_root)
    steering_approvals = [a for a in all_approvals if a.get("category") == "steering"]

    result = {}
    for stem, filename in _STEERING_DOCS:
        fp = st / filename
        identity = _approval_identity(fp)
        if identity is None:
            approved = False
        else:
            canonical, digest = identity
            approved = approvals.has_approved_any(
                steering_approvals, canonical, digest,
                approvals_root, "steering",
            )
        result[stem] = {
            "exists": fp.exists(),
            "approved": approved,
            "lastModified": _file_modified(fp),
        }
    return result


def _collect_reconciliation(root: Path) -> dict:
    """Compare the on-disk specs dir against tracked git entries to surface
    phantoms (tracked with no dir) and orphans (dir with no git history).

    Best-effort — returns empty lists when git isn't available so the
    caller never blocks the agent on environmental edge cases.
    """
    specs_root = root / WORKFLOW_DIR / "specs"
    on_disk = {p.name for p in specs_root.iterdir() if p.is_dir()} if specs_root.is_dir() else set()

    tracked = git.tracked_subdirs(specs_root, root)

    phantom_specs = sorted(tracked - on_disk)
    orphan_dirs = sorted(on_disk - tracked)
    banner_lines: list[str] = []
    if phantom_specs:
        banner_lines.append(
            f"[Advisory] {len(phantom_specs)} phantom spec(s) in git "
            f"with no directory: {', '.join(phantom_specs)}"
        )
    if orphan_dirs:
        banner_lines.append(
            f"[Advisory] {len(orphan_dirs)} orphan directory(ies) not "
            f"tracked in git: {', '.join(orphan_dirs)}"
        )
    banner = "\n".join(banner_lines)
    return {
        "phantom_specs": phantom_specs,
        "orphan_dirs": orphan_dirs,
        "banner": banner,
        "action_required": bool(phantom_specs or orphan_dirs),
    }


def _orphan_spec_directory_advisory(root: Path, spec_name: str) -> dict | None:
    """Advisory for empty spec dirs whose only entries are dot-files.

    Returns ``None`` when the dir is genuinely missing or when it
    contains any ``*.md`` documents (normal partial authoring). Emits
    a structured advisory when the dir exists but looks like residue
    from an aborted prior session (e.g. only ``.reference-ledger.jsonl``
    and ``.gate-session.json``). The envelope names the files so the
    agent can propose removal without scanning the filesystem.
    """
    try:
        sd = paths.spec_dir(root, spec_name)
    except Exception:
        return None
    if not sd.is_dir():
        return None
    entries = []
    has_markdown = False
    for entry in sorted(sd.iterdir()):
        entries.append(entry.name)
        if entry.is_file() and entry.suffix == ".md":
            has_markdown = True
    if not entries or has_markdown:
        return None
    dotfiles = [name for name in entries if name.startswith(".")]
    if not dotfiles:
        return None
    next_action_command = (
        f'rm -r "{sd}"  # Or inspect files and remove selectively'
    )  # noqa: solve-dont-punt — orphan dot-only specs have no SDD script
    # owner; surfacing a literal shell command lets the agent paraphrase
    # to a Read/Glob inspection if it prefers to salvage state.
    return {
        "path": str(sd),
        "files": entries,
        "dotfiles": dotfiles,
        "hint": (
            f"Spec directory '{sd.name}' has no *.md documents but "
            "carries residual dot-files from an aborted prior run. "
            "Remove the directory to clean up, or move the files "
            "aside if they contain salvageable state."
        ),
        "next_action_command": next_action_command,
    }


def _handle_suggest_name(free_text: str, root: Path) -> dict:
    """Return context-aware slug suggestions for ``free_text``.

    Reads ``discovery/*/manifest.json`` via the shared locator so the
    generator sees the same context the agent would read manually —
    honours the "do not fabricate candidates" rule with a context-aware
    path.
    """
    from sdd_core.slug import suggest, build_ask_question_payload
    from discovery.shared import (
        get_discovery_project_names,
        get_discovery_prd_titles,
    )

    specs_root = root / WORKFLOW_DIR / "specs"
    existing = [p.name for p in specs_root.iterdir() if p.is_dir()] if specs_root.is_dir() else []
    archive_root = root / WORKFLOW_DIR / "archive" / "specs"
    archived = [p.name for p in archive_root.iterdir() if p.is_dir()] if archive_root.is_dir() else []

    discovery_projects = get_discovery_project_names(root)
    related_prd_titles = get_discovery_prd_titles(root)

    suggestions = suggest(
        free_text, existing=existing, archived=archived,
        discovery_projects=discovery_projects,
        related_prd_titles=related_prd_titles,
    )
    payload = build_ask_question_payload(free_text, suggestions)
    return {
        "suggestions": [s.to_payload() for s in suggestions],
        "user_question_prompt": payload["user_question_prompt"],
        "ask_question_payload": payload["ask_question_payload"],
        "existing_specs": sorted(existing),
        "archived_specs": sorted(archived),
        "discovery_projects": discovery_projects,
    }


def main() -> None:
    parser = cli.strict_parser(__doc__)
    cli.target_argument(parser, family="spec", required=False)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--type", choices=["steering"])
    parser.add_argument("--verify-logs", action="store_true",
                        help="Cross-check [x] markers against implementation log files")
    parser.add_argument("--reconcile-git-status", action="store_true",
                        help="Surface phantom tracked specs and orphan directories")
    parser.add_argument("--suggest-name", default=None, metavar="FREE_TEXT",
                        help="Suggest kebab-case slug candidates for the given free text")
    parser.add_argument(
        "--include-audit-log", action="store_true",
        help=(
            "Consult approval-audit.log alongside the snapshot/active "
            "ledgers. Default off for backwards compatibility — when "
            "enabled, a phase is reported as approved when either layer "
            "carries a matching record."
        ),
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    if not any([args.spec_name, args.all, args.type, args.reconcile_git_status, args.suggest_name]):
        output.error("Provide --spec-name, --all, --type steering, --reconcile-git-status, or --suggest-name")

    root = paths.require_workflow_root()

    def _emit(payload: dict, msg: str) -> None:
        # The registry's ``review/pipeline-tick:launch`` row declares an
        # ``emitter`` so the rendered command carries every required
        # flag (``--review-skill`` / ``--doc-list``) without a per-script
        # augmentation pass. ``handoffs_for`` resolves the emitter
        # against the bound context.
        rendered = handoffs.handoffs_for(handoffs.current_script_id(), ctx)
        output.success(
            payload,
            msg,
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=rendered,
        )

    if args.suggest_name is not None:
        data = _handle_suggest_name(args.suggest_name, root)
        _emit(data, f"{len(data['suggestions'])} slug suggestion(s)")
        return
    if args.reconcile_git_status:
        data = {"reconciliation": _collect_reconciliation(root)}
        data["banner"] = data["reconciliation"]["banner"]
        count = len(data["reconciliation"]["phantom_specs"]) + len(data["reconciliation"]["orphan_dirs"])
        _emit(data, f"{count} reconciliation finding(s)")
        return

    if args.type == "steering":
        result = check_steering(root)
        _emit(result, "Steering docs status")
    elif args.all:
        results = check_all_specs(
            root, include_audit_log=args.include_audit_log,
        )
        _emit({"specs": results, "count": len(results)}, f"{len(results)} spec(s) found")
    else:
        info = check_single_spec(
            root, args.spec_name,
            include_audit_log=args.include_audit_log,
        )
        # Surface an advisory when the spec directory carries only
        # dot-files (e.g. a stale .reference-ledger.jsonl from an
        # aborted prior run). Computed here so both the "not found" and
        # "found" branches can attach the advisory — detect_spec_phase
        # may report a valid phase even for empty dirs.
        advisory = _orphan_spec_directory_advisory(root, args.spec_name)
        if not info:
            # Absence of a spec is a legitimate first-run state during
            # ``sdd create spec`` — reserve exit 1 + error envelope for
            # true failures (IO errors, corrupt state).
            workspace_dir = root / WORKFLOW_DIR / "workspace" / args.spec_name
            if workspace_dir.is_dir():
                hint = (
                    f"A workspace named '{args.spec_name}' exists. "
                    "Use workspace/check-status.py --target <feature> "
                    "instead of spec/check-status.py --target <spec-name>"
                )
            else:
                hint = "Run spec/check-status.py --all to list all specs"
            payload: dict = {
                "exists": False,
                "specName": args.spec_name,
                "hint": hint,
            }
            if advisory:
                payload["orphan_spec_directory"] = advisory
            _emit(payload, f"Spec not found: {args.spec_name}")
            return  # unreachable — output.success exits
        if args.verify_logs:
            info = _verify_logs(root, args.spec_name, info)
        info["exists"] = True
        if advisory:
            info["orphan_spec_directory"] = advisory
        _emit(info, f"Spec {args.spec_name}: {info['currentPhase']} ({info['overallStatus']})")


if __name__ == "__main__":
    cli.run_main(main)
