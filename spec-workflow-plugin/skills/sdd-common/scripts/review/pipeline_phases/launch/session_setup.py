"""Launch-time session bootstrap, command-map assembly, and choice baselines.

Helpers that the orchestrator calls between precondition gating and
result assembly: gate-session init + ``launch_args_cache`` seeding,
``phase_commands`` / ``prompt_commands`` / ``re_review_commands`` map
construction, the launch-time post-fix user-choice baseline, the
prompt-registry validation advisories, and the single-document
continuation gate.
"""
from __future__ import annotations

import os

from sdd_core import output
from sdd_core.command_templates import build_check_re_review_command
from sdd_core.prompts import load_registry as _load_prompt_registry
from review_quality.constants import (
    SCOPE_PER_DOCUMENT,
    user_choices_for_transition,
)
from review_quality.gate_session import (
    GATE_LAUNCH_ARGS_CACHE,
    GATE_LAUNCH_FLAGS,
    GATE_REVIEW_GATE,
    init_session,
    read_session,
    write_session,
)

from ...phase_kit import PhaseContext
from ..constants import (
    ADVISORY_CODE_PROMPT_REGISTRY_MISSING,
    ADVISORY_CODE_PROMPT_REGISTRY_UNKNOWN_TYPE,
    PHASE_CHECK_REVALIDATION,
    PHASE_POST_FIX,
    PHASE_POST_REVIEW,
    PHASE_PRE_APPROVAL,
)
from .. import build_phase_cmd


# ---------------------------------------------------------------------------
# Command map assembly
# ---------------------------------------------------------------------------


def _build_command_maps(
    project_path: str, category: str, target_name: str,
    doc_list: str, max_fix_cycles: int, lifecycle_flags: str,
) -> tuple[dict, dict, list[str]]:
    """Build prompt_commands, phase_commands, and re_review_commands."""
    re_review_cmds = [
        build_check_re_review_command(
            doc=doc.strip(), spec_name=target_name, category=category,
            project_path=project_path or ".",
        )
        for doc in doc_list.split(",") if doc.strip()
    ]

    prompt_commands = {
        "post_change_review": (
            '.spec-workflow/sdd util/generate-prompt.py '
            '--type post-change-review --params context="<description of changes>"'
        ),
        "review_fix_issues": (
            '.spec-workflow/sdd util/generate-prompt.py '
            '--type review-fix-issues '
            '--params issue_count=<N> context="<summary of issues>"'
        ),
        "fix_loop_continue": (
            '.spec-workflow/sdd util/generate-prompt.py '
            '--type fix-loop-continue '
            f'--params fix_cycle=<N> max_fix_cycles={max_fix_cycles}'
        ),
    }

    phase_commands = {
        "post_review": build_phase_cmd(
            PHASE_POST_REVIEW,
            project_path=project_path,
            category=category,
            target_name=target_name,
            lifecycle_flags=lifecycle_flags,
        ),
        "check_revalidation": build_phase_cmd(
            PHASE_CHECK_REVALIDATION,
            project_path=project_path,
            category=category,
            target_name=target_name,
            extra_args='--doc "<doc_name>"',
            lifecycle_flags=lifecycle_flags,
        ),
        "post_fix": build_phase_cmd(
            PHASE_POST_FIX,
            project_path=project_path,
            category=category,
            target_name=target_name,
            extra_args=f'--doc-list "{doc_list}" --fix-cycle {{fix_cycle}} --max-cycles {max_fix_cycles} --user-choice {{user_choice}}',
            lifecycle_flags=lifecycle_flags,
        ),
        "pre_approval": build_phase_cmd(
            PHASE_PRE_APPROVAL,
            project_path=project_path,
            category=category,
            target_name=target_name,
            extra_args=f'--doc-list "{doc_list}"',
            lifecycle_flags=lifecycle_flags,
        ),
    }

    return prompt_commands, phase_commands, re_review_cmds


def _launch_time_post_fix_user_choices(
    scope: str,
) -> tuple[list[str], list[str]]:
    """Return ``(allowed, excluded)`` for the launch-time baseline.

    At launch the gate has fix_cycle=0 and no findings yet (the
    sub-agent has not run). The allowed set is the deterministic
    baseline the agent can pre-frame off; the post-review envelope
    overrides it once a real findings count is known and the doc may
    have been edited.
    """
    allowed, excluded = user_choices_for_transition(
        scope=scope, fix_cycle=0, findings_count=0,
    )
    return list(allowed), list(excluded)


def _validate_prompt_registry(prompt_commands: dict) -> list[dict]:
    """Return advisories for any unknown prompt_commands references.

    Caller appends the result to ``data.advisories[]`` so the success-path
    stderr stays empty (``2>&1 | jq`` chaining works).
    """
    advisories: list[dict] = []
    try:
        prompt_registry = _load_prompt_registry()
        known_types = prompt_registry.get("prompts", {})
        for cmd_name in prompt_commands:
            prompt_type = cmd_name.replace("_", "-")
            if prompt_type not in known_types:
                advisories.append(output.advisory(
                    f"prompt_commands.{cmd_name} references unknown prompt type "
                    f"'{prompt_type}'",
                    code=ADVISORY_CODE_PROMPT_REGISTRY_UNKNOWN_TYPE,
                ))
    except FileNotFoundError:
        advisories.append(output.advisory(
            "prompt-registry.json not found — skipping prompt type validation",
            code=ADVISORY_CODE_PROMPT_REGISTRY_MISSING,
        ))
    return advisories


def _init_session_and_cache(
    ctx: PhaseContext, *,
    workflow_mode: str, parent_todo_content: str | None,
    review_skill: str, doc_list: str, scope: str, lifecycle_flags: str,
    max_fix_cycles: int,
) -> tuple[dict, dict, int]:
    """Initialise (or resume) the gate session and seed ``launch_args_cache``.

    Returns ``(session, gate, persisted_cycle)`` where gate is the active
    review_gate dict inside the session (same object identity — mutations
    persist after ``write_session``).
    """
    session = init_session(
        category=ctx.category, target_name=ctx.target_name,
        workflow_mode=workflow_mode,
        gate_id=ctx.gate_id or None,
        parent_todo_id=ctx.parent_todo or None,
        parent_todo_content=parent_todo_content,
        max_cycles=max_fix_cycles, project_path=ctx.project_path,
    )
    gate = session[GATE_REVIEW_GATE]
    persisted_cycle = gate.get("fix_cycle", 0)
    session[GATE_LAUNCH_ARGS_CACHE] = {
        "review_skill": review_skill,
        "project_path": ctx.project_path,
        "doc_list": doc_list,
        "category": ctx.category,
        "target_name": ctx.target_name,
        "scope": scope,
        "lifecycle_flags": lifecycle_flags,
    }
    # Persist the *full* original-launch flag set so re-launch literals
    # are byte-equal to the first launch (modulo ``--fix-cycle`` /
    # ``--gate-id`` deltas). ``check_reval`` reads this dict via the
    # canonical ``build_review_launch_command`` emitter — single owner
    # for both first launch and re-launch shapes. Adding a new launch
    # flag is one entry here; the emitter's ``_LAUNCH_FLAG_ORDER``
    # picks it up automatically.
    gate[GATE_LAUNCH_FLAGS] = {
        "review_skill": review_skill,
        "doc_list": doc_list,
        "scope": scope,
        "workflow_mode": workflow_mode,
        "parent_todo": ctx.parent_todo or "",
        "gate_id": ctx.gate_id or "",
        "max_cycles": max_fix_cycles,
    }
    return session, gate, persisted_cycle


def _maybe_enforce_single_doc_stop_gate(
    ctx: PhaseContext, inp, doc_list: str,
) -> None:
    """Surface an ``AskQuestion``-style blocker when a prior gate
    completed under per-document scope and the caller has not yet
    confirmed continuation intent.

    Consumes the marker when ``--confirm-continuation`` is passed so
    the gate does not fire twice. Non-spec categories and markers from
    finished final-scope gates are ignored.
    """
    if ctx.category != "spec":
        return
    # Avoid calling ``read_session`` when no session file exists — it
    # prints an info message to stderr that can interleave with the
    # next ``output.error`` envelope (breaks strict JSON consumers).
    from review_quality.gate_session import session_path as _session_path
    if not os.path.isfile(
        _session_path(ctx.category, ctx.target_name, ctx.project_path),
    ):
        return
    session = read_session(ctx.category, ctx.target_name, ctx.project_path)
    marker = session.get("single_doc_stop_marker")
    if not isinstance(marker, dict) or not marker:
        return

    if inp.confirm_continuation:
        # User acknowledged the continuation — drop the marker and
        # let the launch proceed.
        session.pop("single_doc_stop_marker", None)
        write_session(ctx.category, ctx.target_name, session, ctx.project_path)
        return

    prior_doc = marker.get("doc") or "the prior document"
    new_docs = [d.strip() for d in (doc_list or "").split(",") if d.strip()]
    confirm_cmd_base = (
        f".spec-workflow/sdd review/pipeline-tick.py --phase launch "
        f"--category {ctx.category} --target-name \"{ctx.target_name}\" "
        f"--workspace {ctx.project_path} "
        f"-- --review-skill {inp.review_skill or ''} "
        f"--doc-list \"{doc_list}\" --scope {inp.scope or SCOPE_PER_DOCUMENT} "
        f"--confirm-continuation"
    )
    ask_payload = {
        "user_question_prompt": (
            f"The previous run stopped after approving '{prior_doc}' "
            "under per-document scope. Continue with the next document?"
        ),
        "questions": [
            {
                "id": "single-doc-continuation",
                "prompt": (
                    f"The previous run stopped after approving "
                    f"'{prior_doc}' under per-document scope. "
                    "Continue with the next document?"
                ),
                "options": [
                    {
                        "id": "continue",
                        "label": (
                            f"Continue — launch review for "
                            f"{doc_list or 'the next document'}"
                        ),
                        "next_action_command": confirm_cmd_base,
                    },
                    {
                        "id": "stop",
                        "label": (
                            f"Stop here — the single-document "
                            f"approval of '{prior_doc}' was intentional"
                        ),
                        "next_action_command": None,
                    },
                ],
            }
        ],
    }
    blocking_payload = {
        "status": "blocked",
        "reason": "single_doc_stop_marker_present",
        "single_doc_stop_marker": marker,
        "requested_doc_list": new_docs,
        "prd_lookup_ask_question_payload": ask_payload,
        "ask_question_payload": ask_payload,
        "next_action_command": confirm_cmd_base,
        "instruction": (
            "Ask the user via AskQuestion (see ask_question_payload) "
            "whether the previous single-document approval was "
            "intentional. If they choose 'continue', re-run --phase "
            "launch with --confirm-continuation. If they choose "
            "'stop', leave the workflow as-is."
        ),
    }
    output.success(
        blocking_payload,
        "Launch paused: single-document stop marker present",
    )
