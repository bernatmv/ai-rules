"""Launch envelope assembly helpers.

Builds the launch result dict (``_build_launch_result``), attaches the
stale-doc re-entry TODO payload (``_emit_reentry_todos_if_needed``),
applies block-first redaction when preconditions are unmet
(``_apply_warn_payload``), and stamps the ``prompt_change_status``
field on re-launches (``_apply_prompt_change_status``). Pure
data-assembly — no I/O, no subprocess, no ``output.*`` calls.
"""
from __future__ import annotations

from sdd_core.prompts import (
    build_sub_agent_echo_instruction,
    substitute_sub_agent_echo_placeholders,
)
from review_quality.gate_session import GATE_REENTRY_COUNT, GATE_REVIEW_GATE
from review_quality.todo_lifecycle import (
    build_owned_todo_ids,
    build_owned_todo_ids_note,
    compute_todo_payload,
    displaces_todo_id_hints,
)
from review_quality.constants import SCOPE_PER_DOCUMENT

from .. import WARN_ENVELOPE_PAYLOAD_KEYS, attach_todo_calls
from ..prompt_builder import (
    build_scoring_guidance,
    build_tier2_facet_criteria_by_scope,
)
from .prompt import (
    GATE_PROMPT_KEY,
    PROGRESS_CHECKLIST_KEY,
    _PROGRESS_CHECKLIST,
    _PROMPT_REDACT_KEYS,
    sub_agent_prompt_sha256,
)


# Disambiguated outcome classes for the launch envelope.
OUTCOME_PRECONDITIONS_UNMET = "preconditions_unmet"
OUTCOME_READY = "ready"


def _build_launch_result(
    sub_agent_prompt: str,
    review_skill_path: str,
    verification_file: str,
    assessment_staging_path: str,
    re_review_cmds: list[str],
    prompt_commands: dict,
    phase_commands: dict,
    max_fix_cycles: int,
    persisted_cycle: int,
    scope: str,
    category: str,
    review_type: str,
    doc_list: str,
    parent_todo: str | None = None,
    required_reference_reads: list[dict] | None = None,
    reentry_count: int = 0,
) -> dict:
    """Assemble the launch result dict (separated for testability)."""
    # Collapse echo instruction into the copyable sub_agent_prompt so
    # "Task.prompt MUST begin with data.sub_agent_prompt verbatim"
    # automatically ships the echo contract. When required reference
    # reads are present, the echo also enforces reference_read_sha256.
    echo_instruction = build_sub_agent_echo_instruction(
        required_reference_reads,
    )
    prompt_with_echo = f"{sub_agent_prompt}\n\n{echo_instruction}"
    # Canonical hash is computed over the placeholder form so it stays
    # stable across launches — the verifier (post-review) recomputes
    # from the same canonical form. Placeholders in the agent-visible
    # prompt below are pre-substituted so the launch envelope is
    # literally copyable: the sub-agent sees the concrete hash and
    # echoes it directly, instead of substituting `<hex>` itself.
    canonical_hash = sub_agent_prompt_sha256(prompt_with_echo)
    prompt_for_agent = substitute_sub_agent_echo_placeholders(
        prompt_with_echo,
        prompt_sha256=canonical_hash,
        reference_reads=required_reference_reads,
    )
    result = {
        "sub_agent_prompt": prompt_for_agent,
        "sub_agent_prompt_sha256": canonical_hash,
        # Surface the invariant at the call site so a first-time
        # encounter with "the SHA didn't change after I edited the doc"
        # is documented in the envelope itself, not tribal memory.
        "sub_agent_prompt_sha256_note": (
            "sub_agent_prompt_sha256 hashes the prompt template + facet "
            "list + spec name + project path — it is content-stable "
            "across doc revisions. A fresh launch does not require "
            "re-issuing the Task call when the prompt hasn't changed; "
            "do require it when the doc has changed (the post-review "
            "verifier handles the link)."
        ),
        "review_skill_path": review_skill_path,
        "verification_file": verification_file,
        "assessment_staging_path": assessment_staging_path,
        "re_review_commands": re_review_cmds,
        "prompt_commands": prompt_commands,
        "phase_commands": phase_commands,
        "max_fix_cycles": max_fix_cycles,
        "fix_cycle": persisted_cycle,
        "scope": scope,
        "category": category,
        "progress_checklist_key": PROGRESS_CHECKLIST_KEY,
        "progress_checklist": _PROGRESS_CHECKLIST,
        # Concrete next CLI run after the Task sub-agent returns. Names
        # post-review directly; fix-issues vs pre-approval routing lives
        # on the post-review envelope (only post-review knows the score).
        "next_action_command": phase_commands["post_review"],
        "next_action_command_note": (
            "After the Task sub-agent returns, run next_action_command "
            "(phase_commands.post_review) to fetch the authoritative "
            "artifact_score. The post-review envelope routes to "
            "phase_commands.pre_approval when findings_count=0 and to "
            "prompt_commands.review_fix_issues (substituting {issue_count} "
            "and {review_context}) when findings_count>0."
        ),
        "score_normalization": {
            "instruction": build_scoring_guidance(review_type, doc_list),
            "expected_format": "{total}/{max}",
            "conversion_formula": "scaled = total / max * 100 (percent)",
        },
        # Cross-scope criteria reconciliation: per-document reviews need
        # to know which facets carry different criteria at final scope so
        # the sub-agent can predict scope demotions while the per-doc
        # gate is the only signal available. Empty dict when every facet
        # uses one criterion across scopes.
        "tier2_facet_criteria_by_scope": build_tier2_facet_criteria_by_scope(
            review_type, doc_list,
        ),
    }
    if required_reference_reads:
        result["required_reference_reads"] = required_reference_reads
    # Emit the full pipeline-owned TODO ID set + displacement hints on
    # every launch payload so SKILL.md prose never has to instruct the
    # agent to pre-author a matching `stepN` scaffold. Single authority
    # for tracker IDs — agents mirror what the pipeline emits.
    if parent_todo:
        result["owned_todo_ids"] = build_owned_todo_ids(
            parent_todo, persisted_cycle, reentry_count=reentry_count,
        )
        result["displaces_todo_id_hints"] = displaces_todo_id_hints()
        result["owned_todo_ids_note"] = build_owned_todo_ids_note()
    return result


def _emit_reentry_todos_if_needed(
    result: dict, gate: dict, parent_todo: str | None,
) -> bool:
    """Attach the stale-doc re-entry TODO payload when the gate signals
    a fresh re-entry.

    ``launch`` is the sole emitter of the re-entry TODO payload;
    ``pre_approval`` only bumps ``reentry_count`` before routing here.
    Guarding on ``reentry_count > 0`` makes the emission idempotent
    across replay-style retries.

    Returns ``True`` iff the payload was attached (useful for the
    routing branch).
    """
    if not parent_todo:
        return False
    reentry_count = int(gate.get(GATE_REENTRY_COUNT, 0) or 0)
    if reentry_count <= 0:
        return False
    session_data = {GATE_REVIEW_GATE: gate}
    review_scope = gate.get("review_scope", SCOPE_PER_DOCUMENT)
    todo_result = compute_todo_payload(
        "re_entry", parent_todo, session_data, review_scope=review_scope,
    )
    attach_todo_calls(result, todo_result)
    return True


def _apply_warn_payload(result: dict, warn_payload: dict | None) -> None:
    """Merge precondition warn payload keys into the launch result and
    redact the prompt-block fields when the gate is unmet.

    Block-first envelope: the prompt + SHA + note are removed so an
    agent cannot dispatch off a stale prompt while preconditions are
    pending. ``launch_args_cache.prompt_sha256`` is preserved for
    post-review's integrity check on the next successful launch.
    """
    if not warn_payload:
        result["preconditions_satisfied"] = True
        result["outcome"] = OUTCOME_READY
        return

    for key in WARN_ENVELOPE_PAYLOAD_KEYS:
        if key in warn_payload:
            result[key] = warn_payload[key]
    result["preconditions_satisfied"] = False
    result["outcome"] = OUTCOME_PRECONDITIONS_UNMET
    result["instruction"] = (
        "Run next_action_command_sequence, then re-invoke "
        "--phase launch. Do not dispatch the sub-agent until "
        "the launch envelope's outcome is no longer "
        f"'{OUTCOME_PRECONDITIONS_UNMET}'."
    )
    for redact in _PROMPT_REDACT_KEYS:
        result.pop(redact, None)


def _apply_prompt_change_status(
    result: dict, status: str | None,
) -> None:
    """Stamp the ``prompt_change_status`` field on the launch envelope.

    Absent on first launch (``status is None``) so consumers branch on
    presence rather than memorising a sentinel string.
    """
    if status is not None:
        result["prompt_change_status"] = status
