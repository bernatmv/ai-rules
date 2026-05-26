"""Check / payload shaping for the launch preconditions gate."""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Final, Iterable, Mapping

from sdd_core import reference_acks, reference_ledger
from sdd_core.doc_config import skill_name_for_category
from sdd_core.skill_md_rules import dependencies_for_skill
from review_quality.constants import SCOPE_PER_DOCUMENT

from .ledger import (
    mark_post_change_review_acked,
    mark_post_change_review_presented,
    read_post_change_review_presented,
)
from .policy import (
    DEFAULT_REQUIRED,
    applies,
    enforce_level,
    has_warn_seen_marker,
    precondition_next_action,
    precondition_script,
)
from .types import (
    AnyPrecondition,
    Finding,
    PostChangeReviewPrecondition,
    ReferenceReadPrecondition,
    build_ack_reference_read_command,
)

__all__ = [
    "check",
    "build_missing_payload",
    "build_required_reference_reads",
    "build_ack_reference_read_command",
    "build_recovery_chain",
    "build_pre_launch_sequence",
]


_MISSING_FILE_SENTINEL = "MISSING_FILE"
_SHA_READ_TEMPLATE = (
    '{var}=$(.spec-workflow/sdd util/sha256.py --file {path} --raw)'
)
_SHA_DRIFT_GUARD_TEMPLATE = (
    "[ \"${{{var}}}\" != \"" + _MISSING_FILE_SENTINEL + "\" ] || "
    "{{ echo 'skills-pack-drift detected: {path}' >&2; exit 1; }}"
)
_TODO_ID_FORMAT = "launch-precondition-{idx}-{name}"
_REFERENCE_ACK_TTL_ENV: Final[str] = "SDD_REFERENCE_ACK_MAX_AGE_SECONDS"
_REFERENCE_ACK_DEFAULT_TTL: Final[timedelta] = timedelta(hours=1)
_FREEDOM_TTL: Final[Mapping[str, "timedelta | None"]] = {
    "L": _REFERENCE_ACK_DEFAULT_TTL,
    "M": timedelta(hours=12),
    "H": None,
}


def _reference_ack_default_ttl() -> timedelta:
    raw = os.environ.get(_REFERENCE_ACK_TTL_ENV)
    if not raw:
        return _REFERENCE_ACK_DEFAULT_TTL
    try:
        return timedelta(seconds=int(raw))
    except ValueError:
        return _REFERENCE_ACK_DEFAULT_TTL


def _ttl_for(freedom: str) -> "timedelta | None":
    return _FREEDOM_TTL.get(freedom, _reference_ack_default_ttl())


def _dependency_freedom_for(
    *,
    category: str,
    review_skill: str = "",
    project_path: str = "",
) -> dict[str, str]:
    try:
        skill = review_skill or skill_name_for_category(category)
    except KeyError:
        return {}
    return dependencies_for_skill(skill, project_path=project_path)


def _build_recovery_components(
    reference_findings: list[Finding],
    by_name: dict[str, AnyPrecondition],
    other_findings: list[Finding],
    *, category: str, target_name: str,
    project_path: str, gate_id: str,
    relaunch_command: str,
) -> list[str]:
    """Return the ordered command list that the chain + steps share.

    Single source for the "per-reference SHA → batched ack →
    non-reference recoveries → relaunch" sequence. Both the
    ``&&``-joined string view (:func:`build_recovery_chain`) and the
    array view (:func:`build_recovery_steps`) compose from this list,
    so the two representations stay byte-isomorphic by construction.
    """
    lines: list[str] = []
    ref_preconditions: list[ReferenceReadPrecondition] = []
    for f in reference_findings:
        pre = by_name.get(f.name)
        if not isinstance(pre, ReferenceReadPrecondition):
            continue
        var = f"{f.name.upper()}_SHA"
        path = pre.absolute_path()
        lines.append(_SHA_READ_TEMPLATE.format(var=var, path=path))
        lines.append(_SHA_DRIFT_GUARD_TEMPLATE.format(var=var, path=path))
        ref_preconditions.append(pre)
    batched = build_ack_reference_read_command(
        ref_preconditions,
        category=category, target_name=target_name,
        project_path=project_path, gate_id=gate_id,
        sha_resolver=lambda p: f"${{{p.name.upper()}_SHA}}",
    )
    if batched:
        lines.append(batched)
    for f in other_findings:
        lines.append(f.next_action_command)
    if relaunch_command:
        lines.append(relaunch_command)
    return lines


def build_recovery_chain(
    reference_findings: list[Finding],
    by_name: dict[str, AnyPrecondition],
    other_findings: list[Finding],
    *, category: str, target_name: str,
    project_path: str, gate_id: str,
    relaunch_command: str,
) -> str:
    """Return a ``&&``-joined Bash chain executable in one turn.

    Sequence: per-reference SHA reads → batched ack → non-reference
    precondition recoveries → relaunch. Skipped when no relaunch is
    supplied because a chain without a terminal re-run cannot clear
    the gate on its own.
    """
    lines = _build_recovery_components(
        reference_findings, by_name, other_findings,
        category=category, target_name=target_name,
        project_path=project_path, gate_id=gate_id,
        relaunch_command=relaunch_command,
    )
    return " && \\\n  ".join(lines)


def build_recovery_steps(
    reference_findings: list[Finding],
    by_name: dict[str, AnyPrecondition],
    other_findings: list[Finding],
    *, category: str, target_name: str,
    project_path: str, gate_id: str,
    relaunch_command: str,
) -> list[dict]:
    """Return the array view of :func:`build_recovery_chain`.

    Each step is ``{"name": <stable_id>, "command": <literal>}``. The
    name lifts the ``--phase X`` token when present so consumers can
    dispatch on ``name`` without parsing the command.
    """
    from review._routing import build_phase_steps
    lines = _build_recovery_components(
        reference_findings, by_name, other_findings,
        category=category, target_name=target_name,
        project_path=project_path, gate_id=gate_id,
        relaunch_command=relaunch_command,
    )
    return build_phase_steps(lines)


def _finding_next_action(
    pre: AnyPrecondition,
    *, category: str, target_name: str,
    project_path: str, gate_id: str,
) -> str:
    """Return the user-facing initial action for a missing precondition.

    Reference-read gates surface the ``Read <abs_path>`` directive (the
    agent's first action); every other gate surfaces the recovery shell
    command returned by :func:`precondition_next_action`.
    """
    if isinstance(pre, ReferenceReadPrecondition):
        return pre.read_instruction()
    return precondition_next_action(
        pre,
        category=category, target_name=target_name,
        project_path=project_path, gate_id=gate_id,
    )


def _index_by_script(
    entries: Iterable[reference_ledger.LedgerEntry],
) -> dict[str, reference_ledger.LedgerEntry]:
    index: dict[str, reference_ledger.LedgerEntry] = {}
    for entry in entries:
        if entry.script:
            index[entry.script] = entry  # latest-wins
    return index


def _has_reference_read_entry(
    entries: Iterable[reference_ledger.LedgerEntry],
    pre: ReferenceReadPrecondition,
) -> bool:
    expected_path = pre.absolute_path()
    expected_name = pre.name
    for entry in entries:
        if entry.script == pre.script or entry.script.endswith(expected_path):
            return True
        extra = getattr(entry, "extra", None)
        if isinstance(extra, dict) and extra.get("name") == expected_name:
            return True
    return False


def _post_change_review_present_command(
    *,
    project_path: str = "",
) -> str:
    """Render the present-once recovery command (single owner)."""
    project = project_path or "."
    parts = [
        ".spec-workflow/sdd util/generate-prompt.py",
        "--type post-change-review",
    ]
    if project and project != ".":
        parts.append(f"--workspace {project}")
    return " ".join(parts)


def _handle_post_change_review(
    pre: PostChangeReviewPrecondition,
    *,
    category: str,
    target_name: str,
    project_path: str,
    gate_id: str,
    prompt_sha256: str,
    existing_entry: "reference_ledger.LedgerEntry | None",
) -> "Finding | None":
    """Drive the present-once policy for the post-change-review gate.

    With ``prompt_sha256`` set, missing or stale acks are silently
    (re-)recorded inline (sha-pinned auto-ack — see
    ``test_workspace_scoped_ack``). Without it, a missing ``presented``
    marker for this cycle surfaces the prompt-render Finding; a missing
    workspace ack surfaces the ack recovery shim. The split markers let
    one ack survive across cycles while presentation re-fires once.
    """
    has_acked = existing_entry is not None
    existing_extra = getattr(existing_entry, "extra", None) if existing_entry else None
    stored_sha = ""
    if isinstance(existing_extra, dict):
        stored_sha = str(existing_extra.get("prompt_sha256") or "")
    if prompt_sha256:
        if has_acked and stored_sha and stored_sha != prompt_sha256:
            mark_post_change_review_acked(
                category=category, target_name=target_name,
                gate_id=gate_id or "default", project_path=project_path,
                prompt_sha256=prompt_sha256,
            )
        elif not has_acked:
            mark_post_change_review_acked(
                category=category, target_name=target_name,
                gate_id=gate_id or "default", project_path=project_path,
                prompt_sha256=prompt_sha256,
            )
        return None

    presented = read_post_change_review_presented(
        category=category, target_name=target_name,
        gate_id=gate_id, project_path=project_path,
    )
    if presented is None:
        # First entry into this gate cycle — record the cycle marker
        # *before* returning the Finding so a process death between
        # render and resume still observes the same gate_uuid.
        mark_post_change_review_presented(
            category=category, target_name=target_name,
            gate_id=gate_id or "default", project_path=project_path,
            prompt_sha256=None,
        )
        return Finding(
            severity="error",
            name=pre.name,
            script=precondition_script(pre, gate_id=gate_id),
            why_blocking=pre.why_blocking,
            next_action_command=_post_change_review_present_command(
                project_path=project_path,
            ),
        )
    if has_acked:
        return None
    return Finding(
        severity="error",
        name=pre.name,
        script=precondition_script(pre, gate_id=gate_id),
        why_blocking=pre.why_blocking,
        next_action_command=pre.next_action_command(
            category=category, target_name=target_name,
            project_path=project_path, gate_id=gate_id,
        ),
    )


def check(
    *,
    category: str,
    target_name: str,
    project_path: str = "",
    required: Iterable[AnyPrecondition] = DEFAULT_REQUIRED,
    scope: str = SCOPE_PER_DOCUMENT,
    workflow_mode: str = "create",
    gate_id: str = "",
    prompt_sha256: str = "",
    review_skill: str = "",
) -> list[Finding]:
    """Return one Finding per missing precondition (never raises).

    ``scope`` / ``workflow_mode`` / ``gate_id`` only affect
    :class:`PostChangeReviewPrecondition`. Defaults keep the gate active
    on a fresh ``per-document`` + ``create`` launch.

    ``prompt_sha256`` (when supplied) drives the freshness check on
    the workspace-scoped post-change-review marker: a marker whose
    stored ``prompt_sha256`` extra disagrees with the supplied value
    is treated as stale and silently re-acked with the new sha. When
    omitted, any existing marker satisfies the precondition (legacy
    behaviour).
    """
    entries = reference_ledger.read_entries(category, target_name, project_path)
    index = _index_by_script(entries)
    dependency_freedom = _dependency_freedom_for(
        category=category, review_skill=review_skill, project_path=project_path,
    )
    findings: list[Finding] = []
    for pre in required:
        if not applies(
            pre, category=category, scope=scope, workflow_mode=workflow_mode,
        ):
            continue
        script_id = precondition_script(pre, gate_id=gate_id)
        existing_entry = index.get(script_id)
        if isinstance(pre, PostChangeReviewPrecondition):
            finding = _handle_post_change_review(
                pre,
                category=category, target_name=target_name,
                project_path=project_path, gate_id=gate_id,
                prompt_sha256=prompt_sha256,
                existing_entry=existing_entry,
            )
            if finding is not None:
                findings.append(finding)
            continue
        if script_id in index:
            continue
        if isinstance(pre, ReferenceReadPrecondition) and _has_reference_read_entry(
            entries, pre,
        ):
            continue
        # Project-scoped reference-ack ledger — see sdd_core.reference_acks.
        # Cross-gate ledger auto-satisfies reference-read preconditions
        # when the sha256 matches: once read, never re-demand unless the
        # reference file itself changes content. The per-spec ledger
        # stays authoritative for every non-reference-read precondition.
        if isinstance(pre, ReferenceReadPrecondition):
            current_sha = pre.expected_sha256()
            freedom = dependency_freedom.get(pre.absolute_path(), "L")
            if current_sha and any(
                entry.sha256 == current_sha
                for entry in reference_acks.load_entries(project_path)
            ):
                continue
            if current_sha and reference_acks.is_acked(
                pre.absolute_path(), current_sha,
                project_path=project_path,
                gate_id=gate_id or reference_acks.GLOBAL_GATE_ID,
                max_age=_ttl_for(freedom),
            ) or current_sha and reference_acks.is_acked(
                pre.absolute_path(), current_sha,
                project_path=project_path,
            ):
                # Refresh last_seen_at in the project-scoped ledger and
                # record a mirror entry in the spec-scoped ledger so
                # subsequent post-review/echo checks find the read
                # receipt where they expect it.
                reference_acks.record_ack(
                    pre.absolute_path(), current_sha,
                    project_path=project_path,
                    gate_id=gate_id or reference_acks.GLOBAL_GATE_ID,
                )
                reference_ledger.append_read(
                    category=category, target_name=target_name,
                    project_path=project_path,
                    reference_path=pre.absolute_path(),
                    sha256=current_sha,
                )
                continue
        severity = enforce_level(
            pre, entries,
            category=category, target_name=target_name,
            project_path=project_path,
        )
        previously_warned_in_gate = (
            severity == "error"
            and has_warn_seen_marker(pre, entries)
        )
        findings.append(
            Finding(
                severity=severity,
                name=pre.name,
                script=script_id,
                why_blocking=pre.why_blocking,
                next_action_command=_finding_next_action(
                    pre,
                    category=category, target_name=target_name,
                    project_path=project_path, gate_id=gate_id,
                ),
                previously_warned_in_gate=previously_warned_in_gate,
            )
        )
    return findings


def build_missing_payload(
    findings: Iterable[Finding],
    *,
    category: str = "",
    target_name: str = "",
    project_path: str = "",
    gate_id: str = "",
    required: Iterable[AnyPrecondition] = DEFAULT_REQUIRED,
    relaunch_command: str = "",
) -> dict:
    """Shape the ``missing_preconditions`` block that ``launch`` returns.

    In addition to the per-precondition findings, emit a single
    ``progress_checklist`` the agent can feed straight into ``TodoWrite``
    and a ``next_action_sequence`` array listing the commands in the
    order they should run. Reads run first (they are independent, so the
    agent can batch them in one parallel tool-call turn); ack / shell
    preconditions follow because they mutate gate state.

    Reference-read findings marked ``previously_warned_in_gate``
    receive a paired ``--phase ack-reference-reads`` command so the
    recovery sequence is Read → record (single authority for closing
    the ledger loop). ``category`` / ``target_name`` / ``project_path``
    / ``gate_id`` are only required when a finding carries
    ``previously_warned_in_gate=True``; otherwise the defaults keep the
    function drop-in compatible with call-sites that just wrap findings.
    """
    findings_list = list(findings)
    payload: dict = {
        "missing_preconditions": [f.to_payload() for f in findings_list],
    }

    def _sort_key(finding: Finding) -> tuple[int, str]:
        # Reference reads first (they're the fan-out step); shell acks
        # last (they write ledger state and usually need the reads
        # complete to be meaningful).
        is_read = finding.name.startswith("read_")
        bucket = 0 if is_read else 1
        return (bucket, finding.name)

    by_name = {pre.name: pre for pre in required}
    ordered = sorted(findings_list, key=_sort_key)
    progress_checklist = []
    next_action_sequence = []
    for idx, finding in enumerate(ordered, start=1):
        todo_id = _TODO_ID_FORMAT.format(
            idx=idx, name=finding.name.replace('_', '-'),
        )
        progress_checklist.append({
            "id": todo_id,
            "content": (
                f"{finding.why_blocking} — run: {finding.next_action_command}"
            ),
            "status": "pending",
            "severity": finding.severity,
            "next_action_command": finding.next_action_command,
        })
        next_action_sequence.append(finding.next_action_command)
        # previously_warned_in_gate reference-read findings: append
        # the ack command right after the Read directive so the agent's
        # normal toolbelt clears the ledger (single producer — the shim).
        if finding.previously_warned_in_gate:
            pre = by_name.get(finding.name)
            if isinstance(pre, ReferenceReadPrecondition):
                ack_cmd = build_ack_reference_read_command(
                    [pre],
                    category=category, target_name=target_name,
                    project_path=project_path, gate_id=gate_id,
                )
                if ack_cmd:
                    ack_id = _TODO_ID_FORMAT.format(
                        idx=idx, name=finding.name.replace('_', '-'),
                    ) + "-ack"
                    progress_checklist.append({
                        "id": ack_id,
                        "content": (
                            f"Record read-receipt for {finding.name} "
                            f"— run: {ack_cmd}"
                        ),
                        "status": "pending",
                        "severity": "info",
                        "next_action_command": ack_cmd,
                        "pairs_with": todo_id,
                    })
                    next_action_sequence.append(ack_cmd)

    if progress_checklist:
        payload["progress_checklist"] = progress_checklist
        payload["next_action_sequence"] = next_action_sequence
        payload["progress_instruction"] = (
            "Emit `progress_checklist` via a single `TodoWrite`, then "
            "execute `next_action_sequence` verbatim — reads run first "
            "(parallelisable); each previously-warned read is followed "
            "by its --phase ack-reference-reads command. Finally re-run "
            "`--phase launch` to clear the gate."
        )

    # Copy-paste recovery chain: one Bash turn that reads every
    # reference, records the batched ack, handles non-reference
    # preconditions, and relaunches the gate. Emitted only when the
    # caller supplies a relaunch command because a chain without a
    # terminal relaunch can't clear the gate.
    if relaunch_command and ordered:
        ref_findings = [f for f in ordered if f.name.startswith("read_")]
        other_findings = [f for f in ordered if not f.name.startswith("read_")]
        chain = build_recovery_chain(
            ref_findings, by_name, other_findings,
            category=category, target_name=target_name,
            project_path=project_path, gate_id=gate_id,
            relaunch_command=relaunch_command,
        )
        steps = build_recovery_steps(
            ref_findings, by_name, other_findings,
            category=category, target_name=target_name,
            project_path=project_path, gate_id=gate_id,
            relaunch_command=relaunch_command,
        )
        if chain:
            payload["next_action_command_sequence"] = chain
            payload["next_action_steps"] = steps
            payload["progress_instruction"] = (
                "Execute `next_action_steps[]` (one Bash turn per step "
                "so per-step failures surface) — or, equivalently, run "
                "`next_action_command_sequence` as a single chain. The "
                "sequence computes reference SHAs, records the batched "
                "ack, handles any non-reference preconditions, and "
                "re-runs `--phase launch`."
            )
    return payload


def build_pre_launch_sequence(
    *,
    category: str,
    target_name: str,
    project_path: str = "",
    gate_id: str = "",
    scope: str = SCOPE_PER_DOCUMENT,
    workflow_mode: str = "create",
    required: Iterable[AnyPrecondition] = DEFAULT_REQUIRED,
    missing_names: Iterable[str] = (),
) -> list[dict]:
    """Return a positive ``pre_launch_sequence`` list.

    Describes the canonical precondition ordering so the launch envelope
    surfaces it on every call, not only when a precondition is missing.
    Each entry carries a ``status`` (``satisfied`` / ``missing``) and
    the literal command the agent would run to satisfy it.
    """
    missing_set = {name for name in missing_names if name}
    sequence: list[dict] = []
    for pre in required:
        if not applies(
            pre,
            category=category,
            scope=scope,
            workflow_mode=workflow_mode,
        ):
            continue
        entry: dict = {
            "name": pre.name,
            "status": "missing" if pre.name in missing_set else "satisfied",
            "why": pre.why_blocking,
        }
        if isinstance(pre, ReferenceReadPrecondition):
            entry["read_instruction"] = pre.read_instruction()
            entry["command"] = precondition_next_action(
                pre,
                category=category,
                target_name=target_name,
                project_path=project_path,
                gate_id=gate_id,
            )
        else:
            entry["command"] = precondition_next_action(
                pre,
                category=category,
                target_name=target_name,
                project_path=project_path,
                gate_id=gate_id,
            )
        sequence.append(entry)
    return sequence


def build_required_reference_reads(
    required: Iterable[AnyPrecondition] = DEFAULT_REQUIRED,
    *,
    category: str = "",
    review_skill: str = "",
    project_path: str = "",
) -> list[dict]:
    """Assemble the ``required_reference_reads`` launch payload entries.

    One dict per reference-read gate with the stable identifiers the
    agent needs to echo:

    * ``name`` — matches the precondition / :class:`Finding` name.
    * ``absolute_path`` — path the agent must ``Read``.
    * ``sha256`` — content hash at launch time; empty string when the
      file is unreadable (post-review records a missing-read finding
      rather than a mismatch).
    """
    dependency_freedom = _dependency_freedom_for(
        category=category, review_skill=review_skill, project_path=project_path,
    )
    rows = []
    for pre in required:
        if not isinstance(pre, ReferenceReadPrecondition):
            continue
        abs_path = pre.absolute_path()
        freedom = dependency_freedom.get(abs_path, "L")
        rows.append({
            "name": pre.name,
            "absolute_path": abs_path,
            "sha256": pre.expected_sha256(),
            "freedom": freedom,
        })
    return rows
