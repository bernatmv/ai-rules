#!/usr/bin/env python3
"""Update approval JSON status and write audit log entry.

Usage: update-approval-status.py <approval-json> <action> <response> [--actor <actor>]
Actions: approve, reject, needs_revision
Exit code: 0 success, 1 validation failure, 2 write failure.
"""

import _bootstrap  # noqa: F401

import json
import os

from pathlib import Path as _Path

from sdd_core.time import ts_now
from sdd_core import paths as _paths
from sdd_core import (
    output, cli, command_templates, snapshots, transient_state,
    review_quality_schema as rq_schema,
)
from sdd_core.approval import (
    STATUS_TRANSITIONS,
    canonical_args,
    resolve,
    status_choices as _status_choices,
)
from sdd_core.reference_ledger import hash_file
from sdd_core.security.actor import ActorKind
from sdd_core.security.audit import (
    EVENT_APPROVAL_ATTEMPT_REJECTED,
    EVENT_APPROVAL_STATUS_CHANGE,
    audit_sink,
    build_audit_entry,
)
from sdd_core.security.state import TransactionalStore

from sdd_core import __version__ as SKILL_VERSION


# Action verb that the H1 gate intercepts; only ``approve`` requires a human-actor proof.
ACTION_APPROVE = "approve"
# Default approval category fallback when the record omits ``category`` (legacy rows).
DEFAULT_CATEGORY_SPEC = "spec"
# Status verb the script enforces as the only legal source state for any transition.
STATUS_PENDING = "pending"
# Terminal status that triggers snapshot creation + phase_history append.
STATUS_APPROVED = "approved"
# Terminal status that triggers snapshot creation under the revision-requested trigger.
STATUS_NEEDS_REVISION = "needs_revision"
# Snapshot trigger label used when the user requests revisions on a pending approval.
SNAPSHOT_TRIGGER_REVISION = "revision_requested"
# Audit gate identifier surfaced in both the audit entry and the preflight envelope.
AUDIT_GATE_H1_HUMAN_ACTOR = "h1-human-actor"
# triggerContext metadata: distinguishes status-change emits from approval-confirm flows.
TRIGGER_CONTEXT_SCRIPT_STATUS_CHANGE = "script-status-change"


def _emit_audit(*, type: str, **fields) -> None:
    """Build and emit one audit entry through the canonical sink seam.

    Lazy harness resolution lives in :func:`build_audit_entry`; passing
    ``harness_name=None`` (the default) lets the builder fill it in
    without each caller re-resolving the adapter.
    """
    entry = build_audit_entry(type=type, harness_name=None, **fields)
    try:
        audit_sink().emit(channel="approval", entry=entry)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        output.warn(f"Audit emit ({type}) skipped: {exc}.")


def _check_h1_gate(
    *,
    action: str,
    ctx,
    original: dict,
    json_file: str,
    response_text: str,
    timestamp: str,
    actor: str,
    audit_log: str,
) -> None:
    """Enforce H1 — only a HUMAN actor policy may approve.

    Emits an ``approval-attempt-rejected`` audit entry then a
    ``preflight_required`` envelope. Returns when the gate is not
    triggered (non-approve actions or the human-actor proof is in
    place).
    """
    if action != ACTION_APPROVE or ctx.actor_kind is ActorKind.HUMAN:
        return
    retry_cmd = command_templates.approve_with_human_env(
        approval_file_path=str(json_file),
        response=response_text,
    )
    category_name = original.get("categoryName") or ""
    if category_name:
        _emit_audit(
            type=EVENT_APPROVAL_ATTEMPT_REJECTED,
            actor=actor,
            actor_kind=ctx.actor_kind,
            timestamp=timestamp,
            approval_id=original.get("id"),
            title=original.get("title"),
            filePath=original.get("filePath"),
            category=original.get("category") or DEFAULT_CATEGORY_SPEC,
            categoryName=category_name,
            response=response_text,
            gate=AUDIT_GATE_H1_HUMAN_ACTOR,
            audit_log=audit_log,
            target_name=category_name,
            project_path=str(_paths.find_workflow_root())
            if _has_workflow_root() else "",
        )
    else:
        output.warn(
            f"Audit emit ({EVENT_APPROVAL_ATTEMPT_REJECTED}) skipped: "
            "approval record is missing categoryName."
        )
    output.preflight_required(
        {
            "file": json_file,
            "gate": AUDIT_GATE_H1_HUMAN_ACTOR,
            "approvalId": original.get("id"),
        },
        "Approval gate requires a human actor.",
        error="Approval gate requires a human actor.",
        hint=(
            "Set SDD_HUMAN_APPROVAL=1 in the shell where a human "
            "operator is running the command, or invoke via a SKILL "
            "body that confirms with the approval-confirm-human prompt "
            "first."
        ),
        next_action_command=retry_cmd,
    )


def _verify_drift(
    *, action: str, original: dict, timestamp: str,
) -> "dict | None":
    """Re-hash the live file on approve transitions; refuse drift (C2/C3).

    Returns the verification block to embed in the updated approval JSON,
    or ``None`` when no hash check applies. Raises through ``output.error``
    when drift is detected.
    """
    if action != ACTION_APPROVE:
        return None
    canonical_path_raw = original.get("canonicalPath") or ""
    recorded_hash = original.get("contentHash") or ""
    if not (canonical_path_raw and recorded_hash):
        return None
    live_hash = f"sha256:{hash_file(canonical_path_raw)}"
    if live_hash != recorded_hash:
        category_name = original.get("categoryName") or ""
        if not category_name:
            output.warn(
                "Skipping drift verification: approval record is missing "
                "categoryName."
            )
            return None
        re_request = command_templates.approval_commands(
            title=original.get("title") or "",
            file_paths=[original.get("filePath") or ""],
            category=original.get("category") or DEFAULT_CATEGORY_SPEC,
            target_name=category_name,
        )["request"]
        output.preflight_required(
            {"reason": "doc_drifted_since_request"},
            "Document changed since approval was requested.",
            next_action_command=re_request,
            hint=(
                "Re-request approval against the current bytes; the "
                "gate refuses drifted content."
            ),
        )
    return {
        "state": "current",
        "lastVerifiedAt": timestamp,
        "lastHash": live_hash,
        "reason": "",
    }


def _emit_status_change_audit(
    *,
    action: str,
    original: dict,
    current_status: "str | None",
    new_status: str,
    json_file: str,
    response_text: str,
    timestamp: str,
    audit_log: str,
    actor: str,
    ctx,
) -> None:
    file_path = original.get("filePath", "")
    category_name = original.get("categoryName") or ""
    if not category_name:
        output.warn(
            f"Audit emit ({EVENT_APPROVAL_STATUS_CHANGE}) skipped: "
            "approval record is missing categoryName."
        )
        return
    _emit_audit(
        type=EVENT_APPROVAL_STATUS_CHANGE,
        actor=actor,
        actor_kind=ctx.actor_kind,
        timestamp=timestamp,
        approval_id=original.get("id"),
        title=original.get("title"),
        filePath=file_path,
        category=original.get("category") or DEFAULT_CATEGORY_SPEC,
        categoryName=category_name,
        document=os.path.basename(file_path),
        previousStatus=current_status,
        newStatus=new_status,
        response=response_text,
        previousContent=original,
        audit_log=audit_log,
        target_name=category_name,
        project_path=str(_paths.find_workflow_root())
        if _has_workflow_root() else "",
        metadata={
            "skillVersion": SKILL_VERSION,
            "triggerContext": TRIGGER_CONTEXT_SCRIPT_STATUS_CHANGE,
        },
    )


def _has_workflow_root() -> bool:
    try:
        _paths.find_workflow_root()
    except FileNotFoundError:
        return False
    return True


def _maybe_create_snapshot(
    *, original: dict, new_status: str,
) -> None:
    if new_status not in (STATUS_NEEDS_REVISION, STATUS_APPROVED):
        return
    file_path_val = original.get("filePath", "")
    category_name = original.get("categoryName", "")
    if not (file_path_val and category_name):
        return
    try:
        root = _paths.find_workflow_root()
    except FileNotFoundError:
        return
    full_path = root / file_path_val
    basename = os.path.basename(file_path_val)
    snap_dir = _paths.snapshots_dir(root, category_name, basename)
    trigger = (
        SNAPSHOT_TRIGGER_REVISION if new_status == STATUS_NEEDS_REVISION else STATUS_APPROVED
    )
    try:
        snapshots.create_snapshot(
            full_path, original.get("id", ""), original.get("title", ""),
            trigger, new_status, snap_dir,
            canonical_path=file_path_val,
        )
    except FileNotFoundError as exc:
        output.warn(f"Snapshot skipped — source file not found: {exc}")


def _phase_from_file_path(file_path: str) -> str:
    """Derive the canonical phase name from an approval ``filePath``.

    The phase is the file stem — ``requirements.md`` → ``requirements``,
    ``design.md`` → ``design``. Falls back to the bare basename when no
    extension is present so unrecognised inputs still surface a stable
    label rather than an empty string.
    """
    if not file_path:
        return ""
    base = os.path.basename(file_path)
    stem, _, _ = base.partition(".")
    return stem or base


def _maybe_append_phase_history(
    *, original: dict, new_status: str, timestamp: str,
) -> None:
    """Append a ``phase_history`` entry to the canonical review-quality
    artifact when an approval transitions to ``approved``.

    Bridges the approval pipeline and the review-quality artifact so the
    canonical doc carries the immutable per-phase approval ledger
    without a separate sibling file. No-op when the approval is for a
    non-spec category (steering / discovery), when the spec name is
    empty, or when the artifact file cannot be located — the audit
    trail records the approval regardless via the audit sink.
    """
    if new_status != STATUS_APPROVED:
        return
    category = (original.get("category") or "").strip()
    if category != DEFAULT_CATEGORY_SPEC:
        return
    spec_name = (original.get("categoryName") or "").strip()
    if not spec_name:
        return
    try:
        root = _paths.find_workflow_root()
    except FileNotFoundError:
        return
    artifact_path = root / _paths.review_quality_artifact_path(spec_name)
    try:
        artifact = rq_schema.load(artifact_path)
    except (OSError, ValueError) as exc:
        output.warn(
            f"phase_history append skipped — could not read "
            f"{artifact_path}: {exc}"
        )
        return

    file_path_val = original.get("filePath", "") or ""
    phase = _phase_from_file_path(file_path_val)
    active = rq_schema.get_active(artifact)
    score = active.get("overall_score") if isinstance(active, dict) else None

    entry: dict = {
        "phase": phase,
        "approved_at": timestamp,
    }
    approval_id = original.get("id")
    if approval_id:
        entry["approval_id"] = approval_id
    if score is not None:
        entry["score_at_approval"] = score
    snapshot_ref = original.get("snapshotRef") or original.get("snapshot_ref")
    if snapshot_ref:
        entry["snapshot_ref"] = snapshot_ref
    elif file_path_val:
        # Fall back to the doc filename so consumers can locate the
        # snapshot folder under ``snapshots/<category>/<filename>/`` even
        # when the approval record has no explicit snapshot pointer.
        entry["snapshot_ref"] = os.path.basename(file_path_val)

    rq_schema.append_phase_history(artifact, entry)
    try:
        rq_schema.atomic_write(artifact_path, artifact)
    except OSError as exc:
        output.warn(
            f"phase_history append skipped — could not write "
            f"{artifact_path}: {exc}"
        )


def _run_cleanup(
    *, original: dict, new_status: str,
) -> "transient_state.CleanupReport":
    category_val = original.get("category") or ""
    category_name = original.get("categoryName") or ""
    if not (category_name and new_status in transient_state.APPROVAL_OUTCOMES):
        return transient_state.CleanupReport(
            mode=transient_state.CleanupMode.UNSUPPORTED,
        )
    try:
        project_root = str(_paths.find_workflow_root())
    except FileNotFoundError:
        project_root = ""
    try:
        return transient_state.cleanup_on_approval(
            category=category_val,
            target_name=category_name,
            outcome=new_status,
            project_path=project_root,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        output.warn(
            f"Transient-state cleanup skipped: {exc}. "
            "Approval status update succeeded regardless."
        )
        return transient_state.CleanupReport(
            mode=transient_state.CleanupMode.UNSUPPORTED,
        )


def main() -> None:
    parser = cli.strict_parser(
        "Update approval JSON status and write audit log entry"
    )
    parser.add_argument(
        "approval_json", nargs="?", default=None,
        help="Path to approval JSON file (positional; or --approval-path)",
    )
    parser.add_argument(
        "action", nargs="?", default=None, choices=_status_choices(),
        help="Action to take (positional; or --status). "
             "approved/rejected/needs-revision normalise to "
             "approve/reject/needs_revision.",
    )
    parser.add_argument(
        "response_positional", nargs="?", default=None, metavar="response",
        help="Response text for audit trail (positional; or --response)",
    )
    canonical_args(parser)
    parser.add_argument(
        "--actor", default="ai-agent", help="Actor name for audit log",
    )
    args = parser.parse_args()

    if args.action and not args.status:
        args.status = args.action
    ctx = resolve(args, required_fields=("approval_path", "status", "response"))

    json_file = args.approval_json or ctx.approval_path
    response_text = args.response_positional or ctx.response
    actor = args.actor
    project_root = str(_paths.find_workflow_root()) if _has_workflow_root() else ""
    audit_log = audit_sink().path(
        channel="approval", project_path=project_root,
    ) or ""

    action = ctx.action
    if not json_file or not action or response_text is None:
        output.error(
            "approval_json, action, and response are all required",
            hint=(
                "Positional form: update-status.py <approval.json> <action> <response> "
                "OR flag form: --approval-path <p> --status <s> --response <r>"
            ),
        )

    new_status = STATUS_TRANSITIONS[action]

    if not os.path.isfile(json_file):
        output.error(f"File not found: {json_file}", exit_code=1)

    timestamp = ts_now()

    try:
        with TransactionalStore(json_file) as store:
            try:
                original = store.read_json(default=None)
            except ValueError as exc:
                output.error(str(exc), exit_code=1)
            if original is None:
                output.error(f"File not found: {json_file}", exit_code=1)

            current_status = original.get("status")
            if current_status != STATUS_PENDING:
                output.error(
                    f"Status is '{current_status}', expected '{STATUS_PENDING}'.",
                    exit_code=1,
                )

            _check_h1_gate(
                action=action,
                ctx=ctx,
                original=original,
                json_file=json_file,
                response_text=response_text,
                timestamp=timestamp,
                actor=actor,
                audit_log=audit_log,
            )

            verification_block = _verify_drift(
                action=action, original=original, timestamp=timestamp,
            )

            updated = {
                **original,
                "status": new_status,
                "response": response_text,
                "respondedAt": timestamp,
            }
            if verification_block is not None:
                updated["verification"] = verification_block

            store.write_json(updated, verify_key="status")
    except (OSError, IOError) as e:
        output.error(f"Failed to write {json_file}: {e}", exit_code=2)

    _maybe_create_snapshot(original=original, new_status=new_status)

    _maybe_append_phase_history(
        original=original, new_status=new_status, timestamp=timestamp,
    )

    _emit_status_change_audit(
        action=action,
        original=original,
        current_status=current_status,
        new_status=new_status,
        json_file=json_file,
        response_text=response_text,
        timestamp=timestamp,
        audit_log=audit_log,
        actor=actor,
        ctx=ctx,
    )

    if audit_log and not _Path(audit_log).exists():
        output.warn(
            "Audit emit landed in the canonical ledger only — flat-file "
            "mirror is unavailable for this sink."
        )
        audit_log = ""

    cleanup_report = _run_cleanup(original=original, new_status=new_status)

    payload = {
        "file": json_file,
        "previousStatus": current_status,
        "newStatus": new_status,
        "action": action,
        "cleanup": cleanup_report.to_dict(),
    }
    if audit_log:
        payload["auditLog"] = audit_log
    if ctx.ignored_flags:
        payload["ignored_flags"] = ctx.ignored_flags
    output.success(
        payload,
        f"{json_file} — {current_status} → {new_status}",
    )


if __name__ == "__main__":
    cli.run_main(main)
