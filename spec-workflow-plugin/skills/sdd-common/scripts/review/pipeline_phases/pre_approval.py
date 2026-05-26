"""Pipeline pre-approval phase: check all preconditions before approval prompt."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from sdd_core import output
from sdd_core.paths import doc_dir_path
from review_quality.staleness import (
    check_docs_staleness, _get_mtime_dt, doc_stem, DOC_KEY_SUFFIX,
)
from review_quality.gate_session import (
    GATE_FIX_CYCLE,
    GATE_LAUNCH_ARGS_CACHE,
    GATE_PENDING_CALLS,
    GATE_REENTRY_COUNT,
    GATE_REVIEW_GATE,
    write_session, advance_gate, get_user_accept_time, read_session,
)
from review_quality.cross_validation import find_stale_cross_validation
from review_quality.constants import (
    GateState, TodoStatus, DEFAULT_MAX_FIX_CYCLES,
    DEFAULT_REVIEW_SCOPE,
    MAX_FINDINGS_IN_SUMMARY, SCOPE_PER_DOCUMENT,
)

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from . import (
    SINGLE_DOC_KEYS,
    attach_todo_calls, phase_entry_guard,
    read_artifact_score, load_quality_data,
)
from ._envelope import stamp_reentry_metadata
from .constants import PHASE_PRE_APPROVAL
from .common_validators import (
    require_parent_todo_pair as _require_parent_todo_pair,
)


# Finding-source tags shared with :mod:`review_quality.findings`. Imported
# here as locals so the pre-approval phase keeps a single readable name
# for the source literal without restating the canonical value.
from review_quality.findings import (
    FINDING_SOURCE_FACET_ISSUE as FINDING_SOURCE_FACET,
    FINDING_SOURCE_CROSS_VALIDATION,
    FINDING_SOURCE_TIER1_CHECK as FINDING_SOURCE_TIER1,
)
# advance_gate target when blocking docs force a re-launch ahead of approval.
NEXT_PHASE_LAUNCH = "launch"
# advance_gate target when pre-approval check passes; approval owns the next emit.
NEXT_PHASE_APPROVAL = "approval"
# Side-effect marker the agent / telemetry watch for after the auto-ack opt-in path.
SIDE_EFFECT_AUTO_ACK_CALLS = "auto-ack-calls"


def build_approval_summary(
    quality_data: dict | None,
    artifact_score: dict | None,
    stale_cv_pairs: list[str] | None = None,
    *,
    doc_keys: "set[str] | None" = None,
) -> str:
    """Build the ``summary`` placeholder text for ``approval-formal``.

    When ``doc_keys`` is provided, the summary is filtered to findings
    whose ``doc_key`` matches — cross-document findings are included
    only when at least one side of the pair is in scope, and they are
    visually tagged as ``[cross: a_md ↔ b_md]`` so the approver knows
    the finding is not specific to the doc under review.

    Passing ``doc_keys=None`` surfaces everything (final-scope approval
    path). The returned string is a multi-line summary the registry
    template embeds via the ``{summary}`` substitution.
    """
    if not quality_data:
        return ""

    lines: list[str] = []
    if artifact_score and isinstance(artifact_score, dict):
        score_val = artifact_score.get("value")
        score_max = artifact_score.get("max")
        status = artifact_score.get("status") or quality_data.get("overall_status") or "UNKNOWN"
        if score_val is not None and score_max is not None:
            lines.append(f"Review score: {score_val}/{score_max} ({status}).")
        else:
            lines.append(f"Review status: {status}.")

    filtered_findings = _scoped_findings(quality_data, doc_keys)
    per_facet = [
        f for f in filtered_findings if f["source"] == FINDING_SOURCE_FACET
    ]
    counts: dict[str, int] = {}
    if per_facet:
        for f in per_facet:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    else:
        # Fallback to the issues aggregate the writer surfaces on the
        # active snapshot (v3) — the aggregate is a denormalized
        # convenience so consumers that never loaded ``documents`` can
        # display a counts line without walking the facet arrays.
        top_issues = _resolve_issues_aggregate(quality_data)
        if isinstance(top_issues, dict):
            for sev in ("critical", "warning", "suggestion"):
                n = int(top_issues.get(sev, 0) or 0)
                if n:
                    counts[sev] = n
    parts = [f"{counts[s]} {s}" for s in ("critical", "warning", "suggestion") if counts.get(s)]
    if parts:
        lines.append(f"Key findings: {', '.join(parts)}.")

    top = filtered_findings[:MAX_FINDINGS_IN_SUMMARY]
    if top:
        lines.append("Top findings:")
        for f in top:
            prefix = f.get("prefix") or ""
            lines.append(f"  - [{f['severity']}] {prefix}{f['summary']}")

    if stale_cv_pairs:
        lines.append(
            "[ACTION REQUIRED] cross_doc_flags: stale cross-validation "
            f"pairs {sorted(stale_cv_pairs)} — review may not reflect "
            "current cross-document consistency."
        )

    return "\n".join(lines)


def _resolve_issues_aggregate(quality_data: dict | None) -> dict | None:
    """Return the denormalized ``issues`` count dict, schema-version aware.

    v3 lifts the count aggregate onto ``active.issues`` (alongside the
    per-finding rows). Pre-v3 artifacts persisted the aggregate at the
    envelope's top level. Both cases route through this helper so the
    schema lint stays single-sourced on :mod:`review_quality_schema`.
    """
    from sdd_core import review_quality_schema as _rq_schema
    if not isinstance(quality_data, dict):
        return None
    if quality_data.get("schema_version") == _rq_schema.SCHEMA_VERSION:
        active = _rq_schema.get_active(quality_data)
        issues = active.get("issues") if isinstance(active, dict) else None
        return issues if isinstance(issues, dict) else None
    legacy_envelope = quality_data
    issues = legacy_envelope.get("issues")
    return issues if isinstance(issues, dict) else None


def _scoped_findings(
    quality_data: dict, doc_keys: "set[str] | None",
) -> list[dict]:
    """Return findings scoped to ``doc_keys``.

    Delegates to :mod:`review_quality.findings` for the unified taxonomy
    (per-facet + cross-validation), then filters and annotates
    cross-doc findings. ``doc_keys=None`` returns everything.
    """
    from review_quality.findings import collect_findings

    severity_rank = {
        "critical": 0, "warning": 1, "suggestion": 2,
        "conflict": 0, "duplication": 2, "gap": 1, "drift": 1,
        "advisory": 3,
    }

    collected: list[tuple[int, dict]] = []
    for f in collect_findings(quality_data):
        rank = severity_rank.get(f.severity, 4)
        entry = {
            "source": f.source,
            "severity": f.severity,
            "summary": f.summary,
            "prefix": "",
        }
        if f.source == FINDING_SOURCE_FACET:
            if doc_keys is not None and f.doc_key not in doc_keys:
                continue
        elif f.source == FINDING_SOURCE_CROSS_VALIDATION:
            pair = f.pair
            if doc_keys is not None:
                if pair is None or not any(side in doc_keys for side in pair):
                    continue
            if pair:
                entry["prefix"] = f"[cross: {pair[0]} \u2194 {pair[1]}] "
        elif f.source == FINDING_SOURCE_TIER1:
            if doc_keys is not None and f.doc_key is not None and f.doc_key not in doc_keys:
                continue
        collected.append((rank, entry))

    collected.sort(key=lambda t: t[0])
    return [e for _rank, e in collected]


def _try_auto_ack_pending(
    category: str, spec_name: str, project_path: str,
    parent_todo: str | None, gate_id: str | None,
) -> bool:
    """Opt-in auto-ack: clear pending_tool_calls when the gate invariant
    is provably satisfied for THIS phase's scope.

    Returns ``True`` iff calls were auto-cleared. The behaviour is gated
    on ``SDD_AUTO_ACK_CALLS=1`` until telemetry justifies a default flip.
    Opt-in is deliberate — narrow-bridge: we never silently mutate gate
    state without the opt-in, so agents that batch TodoWrite +
    pre-approval can still surface the normal blocked response by
    default.
    """
    if os.environ.get("SDD_AUTO_ACK_CALLS") != "1":
        return False
    if not parent_todo or not gate_id:
        return False

    session = read_session(category, spec_name, project_path)
    gate = session.get(GATE_REVIEW_GATE) or {}
    pending = gate.get(GATE_PENDING_CALLS) or []
    if not pending:
        return False

    # Only auto-ack when every pending call originated from the current
    # gate. Gate scope is inferred from the gate_id / parent_todo_id
    # fields; entries without explicit scope fall through to the normal
    # blocked response.
    gate_gate_id = gate.get("gate_id")
    gate_parent_todo = gate.get("parent_todo_id")
    if gate_gate_id != gate_id or gate_parent_todo != parent_todo:
        return False

    gate[GATE_PENDING_CALLS] = []
    from review_quality.gate_session import write_session as _write
    _write(category, spec_name, session, project_path)
    return True


def _select_approval_prompt_command(
    *,
    workspace_ctx,
    scope: str,
    doc_list: list[str],
    doc_names: str,
    summary_text: str,
    workspace_path: str,
) -> str:
    """Pick the canonical approval-prompt literal for the current target.

    Routing matrix (closed against new prompt types via the registry):

    | Workspace? | Scope          | doc count | Builder                                  |
    |------------|----------------|-----------|------------------------------------------|
    | yes        | (any)          | (any)     | workspace-batch-approve-phase            |
    | no         | per-document   | 1         | single-doc-approval                      |
    | no         | final          | >=1       | spec-batch-approval                      |
    | no         | per-document   | >1        | spec-batch-approval (batch fallback)     |

    The per-document/>1 fallback exists because the per-doc emitter
    already ships one ``approval_commands_per_doc[]`` entry per doc;
    the prompt-side path only needs a single cohort question, and the
    batch prompt is the registry's expression for that.
    """
    from sdd_core.command_templates import (
        build_single_doc_approval_prompt_command,
        build_spec_batch_approval_prompt_command,
        build_workspace_batch_approve_phase_prompt_command,
    )

    if workspace_ctx is not None:
        return build_workspace_batch_approve_phase_prompt_command(
            doc_list=doc_names,
            feature=workspace_ctx.feature,
            repo_id=workspace_ctx.repo_id,
            summary=summary_text,
        )

    doc_keys = [
        doc_stem(doc) + DOC_KEY_SUFFIX for doc in doc_list if doc
    ]
    # ``{approvalId}`` is the canonical placeholder for the request-time
    # value — pre-approval ships it raw so downstream substitution
    # against ``approval/request.py``'s JSON output remains literal.
    approval_id_placeholder = "{approvalId}"

    if scope == SCOPE_PER_DOCUMENT and len(doc_keys) == 1:
        return build_single_doc_approval_prompt_command(
            approval_id=approval_id_placeholder,
            doc_key=doc_keys[0],
            summary=summary_text,
            workspace_path=workspace_path,
        )

    return build_spec_batch_approval_prompt_command(
        approval_id=approval_id_placeholder,
        doc_keys=doc_keys or [doc_names],
        summary=summary_text,
        workspace_path=workspace_path,
    )


def _handle_pre_approval(
    ctx: PhaseContext, inp: "PreApprovalInput",
) -> None:
    """Check all preconditions before presenting the approval prompt.

    Lifecycle fields arrive via :class:`PhaseContext`; phase-specific
    flags via :class:`PreApprovalInput`.
    """
    spec_name = ctx.target_name
    parent_todo = ctx.parent_todo or None
    gate_id = ctx.gate_id or None

    auto_acked = _try_auto_ack_pending(
        ctx.category, spec_name, ctx.project_path, parent_todo, gate_id,
    )

    session, blocked = phase_entry_guard(
        ctx.category, spec_name, ctx.project_path, PHASE_PRE_APPROVAL,
    )
    if blocked:
        output.success(blocked, blocked["reason"])
        return

    doc_list = [d.strip() for d in inp.doc_list.split(",") if d.strip()]

    doc_directory = doc_dir_path(ctx.category, spec_name, ctx.project_path)
    quality_data = load_quality_data(ctx.category, spec_name, ctx.project_path) or {}
    blocking_docs, _ = check_docs_staleness(doc_list, doc_directory, quality_data)

    gate = session.get(GATE_REVIEW_GATE) or {}
    max_cycles_exhausted = gate.get("current_state") == GateState.MAX_CYCLES_EXHAUSTED

    accept_time = get_user_accept_time(session)
    if accept_time and blocking_docs:
        from datetime import datetime
        accept_dt = datetime.fromisoformat(accept_time.replace("Z", "+00:00"))
        blocking_docs = [
            doc for doc in blocking_docs
            if _get_mtime_dt(os.path.join(doc_directory, doc)) > accept_dt
        ]

    if blocking_docs:
        cached = session.get(GATE_LAUNCH_ARGS_CACHE, {})
        from sdd_core.command_templates import (
            build_check_re_review_command as _build_check_re_review_cmd,
            build_recovery_launch_command as _build_recovery_launch_cmd,
        )
        re_review_cmds = [
            _build_check_re_review_cmd(
                doc=doc, spec_name=spec_name, category=ctx.category,
                project_path=ctx.project_path or ".",
            )
            for doc in blocking_docs
        ]
        re_launch_cmd = _build_recovery_launch_cmd(
            workflow_mode=session.get("workflow_mode") or "create",
            category=ctx.category,
            target_name=spec_name,
            doc_list=cached.get("doc_list", inp.doc_list),
            workspace_path=cached.get("project_path", ctx.project_path),
            parent_todo=parent_todo,
            gate_id=gate_id,
            scope=cached.get("scope", DEFAULT_REVIEW_SCOPE),
        )

        diagnostic = None
        if gate.get(GATE_FIX_CYCLE, 0) > 0 and gate.get("current_state") == GateState.RE_VALIDATE:
            diagnostic = (
                "State is RE_VALIDATE with fix_cycle > 0 — "
                "post-fix phase was likely skipped. "
                "Call --phase post-fix to transition state correctly."
            )

        result = {
            "can_approve": False,
            "blocking_docs": blocking_docs,
            "reason": "Documents modified after last review",
            "required_action": "re-review",
            "re_review_commands": re_review_cmds,
            "next_action_command": re_launch_cmd,
        }
        if diagnostic:
            result["diagnostic"] = diagnostic

        # Signal the re-entry by bumping reentry_count; launch owns the
        # TODO emission so this envelope ships no required_tool_calls.
        if parent_todo:
            gate[GATE_REENTRY_COUNT] = int(gate.get(GATE_REENTRY_COUNT, 0) or 0) + 1
        session = advance_gate(session, required_next_phase=NEXT_PHASE_LAUNCH)
        write_session(ctx.category, spec_name, session, ctx.project_path)

        stamp_reentry_metadata(result, gate)

        output.preflight_required(
            result,
            f"Pre-approval blocked: {len(blocking_docs)} doc(s) need re-review",
            hint=(
                "Documents modified after last review — re-launch required. "
                "Re-run --phase launch with the cached launch args."
            ),
            next_action_command=re_launch_cmd,
            error=f"{len(blocking_docs)} doc(s) modified after review",
        )
        return

    doc_dir = doc_dir_path(ctx.category, spec_name)
    resolved_paths = [f"{doc_dir}/{doc}" for doc in doc_list]

    from sdd_core.command_templates import approval_commands as _approval_cmds
    approval_commands_map = _approval_cmds(
        title=f"{ctx.category.title()}: {spec_name}",
        file_paths=resolved_paths,
        category=ctx.category,
        target_name=spec_name,
    )
    approval_cmd = approval_commands_map["request"]

    doc_names = ", ".join(doc_list)
    cached = session.get(GATE_LAUNCH_ARGS_CACHE) or {}
    scope = gate.get("review_scope") or cached.get("scope", SCOPE_PER_DOCUMENT)
    artifact_score = read_artifact_score(
        ctx.category, spec_name, ctx.project_path, data=quality_data,
    )

    stale_cv_pairs: list[str] = []
    for doc in doc_list:
        stale_cv_pairs.extend(find_stale_cross_validation(quality_data, doc_stem(doc)))

    scope_doc_keys: set[str] | None
    if scope == SCOPE_PER_DOCUMENT:
        scope_doc_keys = {doc_stem(doc) + DOC_KEY_SUFFIX for doc in doc_list}
    else:
        scope_doc_keys = None
    summary_text = build_approval_summary(
        quality_data, artifact_score, stale_cv_pairs,
        doc_keys=scope_doc_keys,
    )
    # Approval is never skippable, regardless of scope: per-doc approvals
    # are evidence for the final-scope approval, not a substitute.
    # Skipping would leave the spec in a half-approved state with no
    # aggregate audit row.
    from sdd_core.command_templates import (
        build_single_doc_approval_prompt_command,
        build_spec_batch_approval_prompt_command,
        build_workspace_batch_approve_phase_prompt_command,
    )
    from sdd_core.workspace import is_workspace_context

    workspace_ctx = is_workspace_context(
        ctx.category, spec_name, ctx.project_path,
    )
    approval_prompt_cmd = _select_approval_prompt_command(
        workspace_ctx=workspace_ctx,
        scope=scope,
        doc_list=doc_list,
        doc_names=doc_names,
        summary_text=summary_text,
        workspace_path=ctx.project_path or ".",
    )

    pre_approval_result = {
        "can_approve": True,
        "artifact_score": artifact_score,
        "blocking_docs": [],
        "stale_cross_validation": stale_cv_pairs,
        "approval_command": approval_cmd,
        "approval_commands": approval_commands_map,
        "approval_prompt_command": approval_prompt_cmd,
        "approval_summary": summary_text,
        "next_action_command": approval_prompt_cmd,
    }

    # Per-scope emitter. ``per-document`` scope ships one approval
    # request literal per doc so the operator's "per doc" reading
    # matches the pipeline's emit cardinality. ``final`` scope keeps
    # the bundled shape so cross-doc package gates retain one aggregate
    # audit row. Both shapes flow through ``approval_commands(...)`` so
    # the underlying CLI contract is identical — only the cardinality
    # changes.
    if scope == SCOPE_PER_DOCUMENT and doc_list:
        per_doc_commands = []
        for doc in doc_list:
            per_doc_map = _approval_cmds(
                title=f"{ctx.category.title()}: {spec_name} — {doc}",
                file_paths=[f"{doc_dir}/{doc}"],
                category=ctx.category,
                target_name=spec_name,
            )
            per_doc_commands.append({
                "doc": doc,
                "command": per_doc_map["request"],
                "commands": per_doc_map,
            })
        pre_approval_result["approval_commands_per_doc"] = per_doc_commands

    if auto_acked:
        # Surface the auto-ack as an observable side-effect so agents /
        # telemetry can monitor the behaviour (AS: *solve, don't punt*
        # — no silent state changes).
        pre_approval_result.setdefault("side_effects", []).append(SIDE_EFFECT_AUTO_ACK_CALLS)

    warnings: list[str] = []
    if max_cycles_exhausted:
        warnings.append(
            f"Last-cycle fixes not re-reviewed (max {gate.get('max_cycles', DEFAULT_MAX_FIX_CYCLES)} cycles exhausted). "
            f"Reject approval if changes were significant."
        )
    if stale_cv_pairs:
        warnings.append(
            f"Cross-validation stale for pairs: {stale_cv_pairs}. "
            f"Review may not reflect current cross-document consistency."
        )
    if warnings:
        pre_approval_result["warnings"] = warnings

    # ``approval/update-status.py`` is the sole cleanup owner. ``--phase
    # complete`` remains callable for diagnostic recovery of stuck gates,
    # but the pre-approval envelope no longer emits it as the happy-path
    # follow-up to avoid wasted no-op calls.

    session = advance_gate(session, required_next_phase=NEXT_PHASE_APPROVAL)
    write_session(ctx.category, spec_name, session, ctx.project_path)

    if parent_todo:
        from review_quality.todo_lifecycle import has_completed_work, finalize_active_todos
        active = gate.get("active_todos", [])
        if active:
            work_done = has_completed_work(active)
            terminal_status = TodoStatus.COMPLETED if work_done else TodoStatus.CANCELLED
            orphans = finalize_active_todos(active, terminal_status)
            if orphans:
                attach_todo_calls(pre_approval_result, {
                    "todo_write_payload": {"todos": orphans, "merge": True},
                })

    output.success(pre_approval_result, "Pre-approval check passed — ready for approval")


@dataclass
class PreApprovalInput(PhaseInput):
    """Typed input for the ``pre-approval`` phase.

    The XOR-pairing invariant lives on :meth:`__post_init__`.
    Lifecycle fields mirror the common parent parser so the validator
    has the values it needs; they are not re-exposed as CLI flags.
    """

    doc_list: str = field(
        default=None, metadata={"help": "Comma-separated document list"},
    )
    parent_todo: Optional[str] = None
    gate_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_parent_todo_pair(self.parent_todo, self.gate_id)


@phase(
    name=PHASE_PRE_APPROVAL,
    emits=frozenset({"approval", "launch"}),
    help="Check all preconditions before the approval prompt",
    description=__doc__,
)
class PreApprovalPhase(Phase):
    """Pre-approval gate — runs every readiness check before the
    external approval flow takes over.
    """

    Input = PreApprovalInput

    def handle(self, ctx: PhaseContext, inp: PreApprovalInput) -> None:
        _handle_pre_approval(ctx, inp)
