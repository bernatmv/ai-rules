"""Launch precondition gating + requirements pre-check helpers.

Owns the launch-time precondition gate: the requirements antipattern
pre-check (``_run_requirements_pre_check``), the inline auto-run of
``util/detect-doc-state.py``, the warn / error escalation logic
(``_run_launch_preconditions``), and the review-type resolver
(``_resolve_review_type``). Everything that decides "should this
launch proceed?" lives here so the orchestrator stays narrative.
"""
from __future__ import annotations

import os

from sdd_core import output
from sdd_core.doc_config import DOCUMENT_REGISTRY
from sdd_core.pre_check import (
    build_launch_notes,
    run_requirements_precheck,
    should_run_requirements_check,
)

from review_quality.constants import SCOPE_PER_DOCUMENT

from ...phase_kit import PhaseContext
from ..constants import (
    ADVISORY_CODE_LAUNCH_PRECONDITIONS_WARN,
    KEY_ADVISORIES,
)
from .. import launch_preconditions as _launch_pre


_SKILL_TO_REVIEW_TYPE = {
    reg["skill_name"]: rtype
    for rtype, reg in DOCUMENT_REGISTRY.items()
}


# ---------------------------------------------------------------------------
# Pre-check helpers (see pre-approval-validation.md § Check 1c)
# ---------------------------------------------------------------------------


def _doc_list_contains_requirements(doc_list: str) -> bool:
    """Detect whether requirements.md is among the docs this launch targets."""
    for doc in (doc_list or "").split(","):
        if should_run_requirements_check(doc.strip(), "spec"):
            return True
    return False


def _run_requirements_pre_check(
    *,
    doc_list: str,
    category: str,
    spec_name: str,
    project_path: str,
) -> dict | None:
    """Run the requirements antipattern pre-check when applicable.

    Blocks (via ``output.error``) when the script reports errors.
    Returns a ``pre_check_notes`` dict when the check produced warnings
    or info findings (agents and sub-agents see it in the launch payload).
    Returns ``None`` when there is nothing to report (pass) or when the
    check does not apply to this launch.
    """
    if category != "spec":
        return None
    if not _doc_list_contains_requirements(doc_list):
        return None

    result = run_requirements_precheck(
        spec_name=spec_name, project_path=project_path,
    )
    if not result.get("ran"):
        return None

    exit_code = result.get("exit_code")
    if exit_code == 1:
        from sdd_core.command_templates import build_review_pipeline_launch_command
        recovery_cmd = build_review_pipeline_launch_command(
            target_name=spec_name,
            category=category,
            workspace_path=project_path or ".",
        )
        problems = [
            f"requirements antipattern check failed: "
            f"{result.get('message') or 'see issues'}",
        ]
        output.recoverable_miss(
            {
                "reason": "requirements_antipatterns_blocking",
                "blocking_check": "requirements-antipatterns",
                "spec_name": spec_name,
                "counts": result.get("counts"),
                "issues": result.get("issues") or [],
                "findings": result.get("findings") or [],
                "findings_file": result.get("findings_file"),
                "exit_code": exit_code,
            },
            problems[0],
            next_action_command_sequence=recovery_cmd,
            problems=problems,
            hint=(
                f"{problems[0]} Fix structural / path errors in "
                "requirements.md and re-run launch. Read "
                "`findings_file` to replay findings without re-running "
                "the validator — execute next_action_command_sequence, "
                "then retry."
            ),
        )
    if exit_code not in (0,):
        output.error(
            f"requirements antipattern check errored (exit {exit_code}): {result.get('message') or ''}",
            hint="Inspect lint-requirements.py output and retry.",
        )

    return build_launch_notes(result)


def _env_preconditions_disabled() -> bool:
    """Escape hatch so tests can opt out of the preconditions gate."""
    return os.environ.get("SDD_LAUNCH_PRECONDITIONS") == "0"


def _env_preconditions_enforce() -> bool:
    """When ``SDD_LAUNCH_PRECONDITIONS_ENFORCE=1``, missing preconditions
    escalate to ``output.error`` on the first offence instead of emitting
    a warn marker. Used by tests that need the hard-block branch."""
    return os.environ.get("SDD_LAUNCH_PRECONDITIONS_ENFORCE") == "1"


def _build_relaunch_command(
    ctx: PhaseContext, *, scope: str, workflow_mode: str,
    gate_id: str, review_skill: str = "", doc_list: str = "",
) -> str:
    """Build the ``pipeline-tick.py --phase launch`` command that the
    recovery chain tails. Empty review_skill or doc_list yields an
    empty string so the chain emitter falls back to the per-finding
    ``next_action_sequence`` path."""
    if not (review_skill and doc_list):
        return ""
    from sdd_core.command_templates import build_review_launch_command
    parent_todo = ctx.parent_todo or "step4"
    return build_review_launch_command(
        launch_flags={
            "review_skill": review_skill,
            "doc_list": doc_list,
            "scope": scope,
            "workflow_mode": workflow_mode,
            "parent_todo": parent_todo,
            "gate_id": gate_id or "default",
        },
        locator={
            "category": ctx.category,
            "target_name": ctx.target_name,
            "project_path": ctx.project_path or ".",
        },
    )


def _record_warn_markers(
    findings: list, ctx: PhaseContext,
) -> None:
    """Persist per-finding warn-seen markers so the next call escalates."""
    has_non_read_finding = False
    for finding in findings:
        pre = _launch_pre.find_precondition(finding.name)
        if isinstance(pre, _launch_pre.ReferenceReadPrecondition):
            _launch_pre.mark_read_warn_seen(
                pre=pre,
                category=ctx.category,
                target_name=ctx.target_name,
                project_path=ctx.project_path,
            )
        else:
            has_non_read_finding = True
    if has_non_read_finding:
        _launch_pre.mark_warn_seen(
            category=ctx.category,
            target_name=ctx.target_name,
            project_path=ctx.project_path,
        )


def _env_auto_detect_doc_state() -> bool:
    """Return True when auto-run of detect-doc-state is enabled.

    Default on. Set ``SDD_PIPELINE_AUTO_DETECT_DOC_STATE=0`` to opt out
    (tests that exercise the legacy "warn on first miss" behaviour).
    """
    return os.environ.get("SDD_PIPELINE_AUTO_DETECT_DOC_STATE", "1") != "0"


def _auto_run_detect_doc_state(ctx: PhaseContext, gate_id: str) -> bool:
    """Invoke ``util/detect-doc-state.py`` inline and return success.

    Same bootstrap pattern as :func:`sdd_core.pre_check.run_requirements_precheck`
    — the phase handler owns the subprocess boundary so the precondition
    gate stays pure. Returns True when the subprocess exits 0 so the
    caller can re-run the precondition check once.
    """
    import subprocess as _subprocess
    import sys as _sys
    from pathlib import Path as _Path
    script = _Path(__file__).resolve().parent.parent.parent.parent / "util" / "detect-doc-state.py"
    if not script.is_file():
        return False
    cmd = [
        _sys.executable, str(script),
        "--category", ctx.category,
        "--target-name", ctx.target_name or "",
        "--workspace", ctx.project_path or ".",
    ]
    if gate_id:
        cmd.extend(["--gate-id", gate_id])
    try:
        proc = _subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, _subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _run_launch_preconditions(
    ctx: PhaseContext, *, scope: str = SCOPE_PER_DOCUMENT,
    workflow_mode: str = "create", gate_id: str = "",
    review_skill: str = "", doc_list: str = "",
) -> dict | None:
    """Short-circuit via ``output.error`` when the preconditions gate fails.

    Warn offence returns the ``build_missing_payload`` dict so
    :func:`_handle_launch` merges it into the success envelope; error
    offence calls :func:`sdd_core.output.error` and never returns.
    ``SDD_LAUNCH_PRECONDITIONS_ENFORCE=1`` escalates warn to error on
    the first offence.

    When only ``detect_doc_state`` is missing and
    ``SDD_PIPELINE_AUTO_DETECT_DOC_STATE`` is not ``0``, the handler runs
    the script inline once and re-checks — so a fresh spec clears the
    gate in the same launch call instead of requiring a manual retry.
    """
    if _env_preconditions_disabled():
        return None
    findings = _launch_pre.check(
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=ctx.project_path,
        scope=scope,
        workflow_mode=workflow_mode,
        gate_id=gate_id,
        review_skill=review_skill,
    )
    if (
        findings
        and _env_auto_detect_doc_state()
        and any(f.name == "detect_doc_state" for f in findings)
        and ctx.category == "spec"
        and ctx.target_name
    ):
        if _auto_run_detect_doc_state(ctx, gate_id):
            findings = _launch_pre.check(
                category=ctx.category,
                target_name=ctx.target_name,
                project_path=ctx.project_path,
                scope=scope,
                workflow_mode=workflow_mode,
                gate_id=gate_id,
                review_skill=review_skill,
            )
    if not findings:
        return None

    relaunch_command = _build_relaunch_command(
        ctx, scope=scope, workflow_mode=workflow_mode, gate_id=gate_id,
        review_skill=review_skill, doc_list=doc_list,
    )
    payload = _launch_pre.build_missing_payload(
        findings,
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=ctx.project_path,
        gate_id=gate_id,
        relaunch_command=relaunch_command,
    )
    # Surface the canonical pre-launch ordering on the blocked envelope
    # too — agents inspecting a blocked launch see the same positive
    # sequence shape they'd see on a successful one.
    pre_launch_sequence = _launch_pre.build_pre_launch_sequence(
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=ctx.project_path,
        gate_id=gate_id,
        scope=scope,
        workflow_mode=workflow_mode,
        missing_names=[f.name for f in findings],
    )
    if pre_launch_sequence:
        payload["pre_launch_sequence"] = pre_launch_sequence
    severities = {f.severity for f in findings}
    enforce = _env_preconditions_enforce() or "error" in severities

    if enforce:
        # A recoverable miss carries a recovery sequence — the envelope
        # is structurally result-class so the agent runs the sequence
        # rather than surfacing an error-class traceback.
        sequence = payload.get("next_action_command_sequence", "") or relaunch_command
        output.recoverable_miss(
            payload,
            "launch blocked: missing required preconditions",
            next_action_command_sequence=sequence,
            hint=(
                "Execute `missing_preconditions.next_action_command_sequence`, "
                "then retry --phase launch."
            ),
        )
    payload.setdefault(KEY_ADVISORIES, []).append(
        output.advisory(
            "launch preconditions not met (warn — next call will block). "
            "See `missing_preconditions` on the envelope and execute "
            "`next_action_command_sequence`.",
            code=ADVISORY_CODE_LAUNCH_PRECONDITIONS_WARN,
        )
    )
    _record_warn_markers(findings, ctx)
    return payload


# ---------------------------------------------------------------------------
# Review type resolution
# ---------------------------------------------------------------------------


def _resolve_review_type(review_skill: str) -> str:
    """Return the review type for a given skill or ``output.error`` out."""
    review_type = _SKILL_TO_REVIEW_TYPE.get(review_skill)
    if review_type is None:
        output.error(
            f"Unknown review skill '{review_skill}' — not in DOCUMENT_REGISTRY",
            hint=f"Known skills: {sorted(_SKILL_TO_REVIEW_TYPE)}",
        )
    return review_type
