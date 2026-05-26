"""Pipeline post-review phase: read artifact score after sub-agent review."""
from __future__ import annotations

import re as _re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from sdd_core import output, reference_ledger
from sdd_core.prompts import (
    PIPELINE_INSTRUCTION_CLEAR,
    PIPELINE_INSTRUCTION_PENDING,
    render_pipeline_instruction,
)
from review_quality.gate_session import (
    write_session, advance_gate,
    set_phase_snapshot,
    phase_cache_key, hash_quality_artifact,
    read_session,
)
from review_quality.todo_lifecycle import compute_todo_payload
from review_quality.constants import (
    GateState, INITIAL_FIX_CYCLE, USER_CHOICE_ALLOWED,
    user_choices_for_transition, SCOPE_PER_DOCUMENT,
)
from review_quality.findings import (
    actionable_finding_count, advisory_finding_count, collect_findings,
    findings_by_source_severity,
    count_findings_in_artifact, findings_present,
)
from review_quality.constants import (
    STATUS_FROM_COUNTS,
    _PASS_TOKENS,
)
from review_quality.staleness import DOC_KEY_SUFFIX

# Sentinel surfaced on envelopes when no artifact is available to score
# (blocked / missing-artifact paths). Mirrors the contract of
# :func:`count_findings_in_artifact`: -1 means "nothing scored", 0 means
# "scored, no findings", >0 means "actionable findings present".
FINDINGS_COUNT_UNSCORED = -1

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from ..snapshots import PostReviewSnapshot
from .._routing import (
    maybe_append_ack_calls, replay_snapshot, route_with_ack, build_phase_chain,
)
from ..transitions import phase_key
from . import (
    phase_entry_guard, read_scoped_score, load_quality_data,
    build_phase_cmd, build_prompt_cmd,
    attach_todo_calls, persist_pending_calls,
)
from .constants import PHASE_POST_FIX, PHASE_POST_REVIEW, PHASE_PRE_APPROVAL
from .launch import (
    POST_FIX_USER_CHOICES_SOURCE_POST_REVIEW,
    _compute_doc_list_sha,
)
from .common_validators import (
    require_parent_todo_pair as _require_parent_todo_pair,
)
from . import launch_preconditions as _lp
from review_quality.constants import STRUCTURAL_NA_PREFIX

# Verification finding kinds surfaced on the post_review envelope when
# the sub-agent's echoed hashes disagree with the launch-time values.
# ``str`` base so JSON serialisation still emits the stable wire string
# without callers needing ``.value``.
class EchoFindingKind(str, Enum):
    PROMPT = "sub_agent_echo_mismatch"
    REFERENCE = "reference_read_mismatch"
    REFERENCE_MISSING_ECHO = "reference_read_missing_echo"
    VERDICT_MISMATCH = "sub_agent_verdict_mismatch"


from .constants import TRIVIAL_ADVANCE_INSTRUCTION, TRIVIAL_ADVANCE_LABEL


def _doc_unchanged_since_launch(session: dict, ctx: PhaseContext) -> bool:
    """True when the doc set hasn't changed since the launch snapshot.

    Compares the cached ``last_doc_sha`` (persisted by ``launch.py``)
    to a freshly-computed sha over the same doc list. Missing cache
    entry returns ``False`` so legacy sessions take the safe long
    path.
    """
    cached = session.get("launch_args_cache") or {}
    prior_sha = str(cached.get("last_doc_sha") or "")
    if not prior_sha:
        return False
    doc_list = cached.get("doc_list", "") or ""
    if not doc_list:
        return False
    current_sha = _compute_doc_list_sha(
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=cached.get("project_path") or ctx.project_path,
        doc_list=doc_list,
    )
    return current_sha == prior_sha


def _trivial_advance_to_pre_approval(result: dict) -> bool:
    """Collapse the zero-findings post-review chain into a single sequence.

    Stamps ``next_action_command_sequence``, the operator-facing
    instruction, and a ``trivial_advance`` block onto *result* when
    every downstream leg is present. Routes through the single owner
    of the chain shape (:func:`build_trivial_advance_chain`).
    """
    from .._routing import build_trivial_advance_chain
    phase_cmds = result.get("phase_commands") or {}
    chain_pair = build_trivial_advance_chain(phase_cmds, TRIVIAL_ADVANCE_LABEL)
    if chain_pair is None:
        return False
    chain, label = chain_pair
    result["next_action_command_sequence"] = chain
    result["next_action_command_sequence_label"] = label
    result["next_action_command"] = phase_cmds.get(
        "pre_approval", result.get("next_action_command", ""),
    )
    result["trivial_advance"] = {
        "label": label,
        "folded_phases": ["ack_calls", "check_revalidation", "pre_approval"],
        "next_action_command": phase_cmds.get("pre_approval", ""),
    }
    result["instruction"] = TRIVIAL_ADVANCE_INSTRUCTION
    return True


# Routing copy lives in `prompt-registry.json` under
# `pipeline-instruction-pending` / `pipeline-instruction-clear`.
# Scenarios consumed here: `zero_findings` and `findings`; the
# `post_fix` scenario is consumed by `post_fix.py`.


def _extract_echo_block(data: dict | None) -> dict | None:
    """Return the sub-agent's echo block if present.

    The echo instruction injected into ``sub_agent_prompt`` asks the
    sub-agent to emit a ``sub_agent_prompt_sha256: <hex>`` line plus one
    ``reference_read_sha256: <name> <hex>`` line per
    ``required_reference_reads`` entry. The review-quality writer
    captures these under ``sub_agent_echo`` so we can verify the reply
    came from an unmodified launch envelope.
    """
    if not isinstance(data, dict):
        return None
    block = data.get("sub_agent_echo")
    if not isinstance(block, dict):
        return None
    return block


def _verify_sub_agent_echo(
    session: dict, quality_data: dict | None,
    *,
    category: str = "",
    target_name: str = "",
    project_path: str = "",
) -> list[dict]:
    """Return verification findings (empty when no echo claim is present).

    Absent ``sub_agent_echo`` block: returns ``[]`` so older artifacts
    without the echo contract stay valid. Findings only fire when the
    sub-agent *did* provide a hash and it disagreed with the cached
    expected value.
    """
    echo = _extract_echo_block(quality_data)
    if echo is None:
        return []

    cached = (session.get("launch_args_cache") or {})
    expected_prompt_hash = cached.get("prompt_sha256")
    expected_reads = {
        entry.get("name"): entry.get("sha256")
        for entry in (cached.get("required_reference_reads") or [])
        if isinstance(entry, dict) and entry.get("name")
    }

    findings: list[dict] = []
    echoed_prompt_hash = echo.get("prompt_sha256")
    if (
        expected_prompt_hash
        and echoed_prompt_hash
        and echoed_prompt_hash != expected_prompt_hash
    ):
        findings.append(
            {
                "kind": EchoFindingKind.PROMPT.value,
                "expected": expected_prompt_hash,
                "echoed": echoed_prompt_hash,
                "remediation": (
                    "Sub-agent prompt was modified in transit. Re-run "
                    "--phase launch and ensure Task.prompt begins with "
                    "data.sub_agent_prompt byte-for-byte."
                ),
            }
        )

    echoed_reads_raw = echo.get("reference_reads")
    echoed_reads: dict[str, str] = {}
    if isinstance(echoed_reads_raw, dict):
        echoed_reads = {
            str(k): str(v) for k, v in echoed_reads_raw.items() if v
        }
    elif isinstance(echoed_reads_raw, list):
        for entry in echoed_reads_raw:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            sha = entry.get("sha256")
            if name and sha:
                echoed_reads[str(name)] = str(sha)

    # Resolve reference paths by name once so a successful sub-agent
    # echo can auto-close the ledger — one of two producers for
    # ``reference_ledger.append_read`` (the other is the
    # ``--phase ack-reference-reads`` shim).
    for name, echoed_sha in echoed_reads.items():
        expected_sha = expected_reads.get(name)
        if expected_sha and echoed_sha and echoed_sha != expected_sha:
            findings.append(
                {
                    "kind": EchoFindingKind.REFERENCE.value,
                    "name": name,
                    "expected": expected_sha,
                    "echoed": echoed_sha,
                    "remediation": (
                        f"Reference '{name}' content hash mismatch — "
                        "re-read the absolute_path emitted in "
                        "required_reference_reads."
                    ),
                }
            )
            continue
        if (
            expected_sha
            and echoed_sha
            and echoed_sha == expected_sha
            and category
            and target_name
        ):
            pre = _lp.find_precondition(name)
            if isinstance(pre, _lp.ReferenceReadPrecondition):
                reference_ledger.verify_and_record_read(
                    name=name,
                    expected_sha256=expected_sha,
                    echoed_sha256=echoed_sha,
                    category=category,
                    target_name=target_name,
                    reference_path=pre.absolute_path(),
                    project_path=project_path,
                )

    # An echo block that includes the prompt hash but no
    # reference_reads dict, when the launch envelope did ship
    # ``required_reference_reads``, indicates the sub-agent's echo
    # omitted the ``reference_read_sha256`` lines the launch envelope
    # advertised. Emit an informational finding so the agent can point
    # the sub-agent at the current echo contract without hard-blocking
    # the post-review.
    if expected_reads and not echoed_reads:
        missing_names = sorted(expected_reads.keys())
        findings.append(
            {
                "kind": EchoFindingKind.REFERENCE_MISSING_ECHO.value,
                "names": missing_names,
                "remediation": (
                    "Sub-agent did not echo `reference_read_sha256` lines. "
                    "Re-launch so the sub-agent sees the updated echo "
                    "instruction and echoes one hash per "
                    "`required_reference_reads` entry."
                ),
            }
        )
    return findings


_INCOMPLETE_TOKEN = "INCOMPLETE"


# Lifts the overall-status token from the canonical headline narrative.
# The shape is owned by
# :data:`review.pipeline_phases.templates.OVERALL_STATUS_NARRATIVE_TEMPLATE` —
# anchor the regex on the literal prose so a drift in either side is
# observable here.
_NARRATIVE_HEADLINE_RE = _re.compile(
    r"Reviewed-docs status:\s*(?P<status>[A-Z_]+)\s*\("
)


def _summarise_tier1(data: "dict | None") -> str:
    """Compact representation of Tier 1 facet outcomes.

    The Tier 1 surface lives under per-document slots in v3
    (``by_scope.per-document.<key>.facets``) and under
    ``documents[*].facets`` for v1/v2 fixtures. The headline summary
    just counts pass / fail / na so the user-facing line stays one row
    regardless of doc count.
    """
    from sdd_core import review_quality_schema as _rq_schema
    if not isinstance(data, dict):
        return "unknown"
    review_type = str(data.get("review_type") or "")
    try:
        from review_quality.registry import tier1_facets_for_type
        tier1_ids = set(tier1_facets_for_type(review_type))
    except Exception:
        return "unknown"
    counts = {"pass": 0, "fail": 0, "na": 0}

    if data.get("schema_version") == _rq_schema.SCHEMA_VERSION:
        for view in _rq_schema.iter_per_doc_active_views(data):
            for facet in view.get("facets") or ():
                _accumulate_tier1_facet(facet, tier1_ids, counts)
    else:
        documents = _legacy_documents(data) or {}
        for doc in documents.values():
            if not isinstance(doc, dict):
                continue
            for facet in (doc.get("facets") or ()):
                _accumulate_tier1_facet(facet, tier1_ids, counts)
    return f"{counts['pass']} pass / {counts['fail']} fail / {counts['na']} na"


def _accumulate_tier1_facet(
    facet, tier1_ids: set, counts: dict[str, int],
) -> None:
    if not isinstance(facet, dict):
        return
    if facet.get("id") not in tier1_ids:
        return
    score = str(facet.get("score") or "").lower()
    if score in counts:
        counts[score] += 1


def _render_gate_score_headline(
    artifact_score: "dict | None", data: "dict | None",
) -> str:
    """Compose the canonical gate-authored headline.

    The agent must echo this verbatim — it is no longer the agent's
    job to compute the score string. Routing only honours
    ``artifact_score`` (server-authoritative); the headline is the
    user-facing narrative the agent presents.
    """
    if not isinstance(artifact_score, dict):
        return "Reviewed-docs status: UNKNOWN (artifact unavailable)"
    status = str(artifact_score.get("status") or "UNKNOWN").upper()
    value = artifact_score.get("value")
    max_value = artifact_score.get("max")
    percent = artifact_score.get("percent")
    tier1_summary = _summarise_tier1(data)
    score_part = (
        f"gate score: {value}/{max_value}"
        + (f" ({percent}%)" if percent is not None else "")
    )
    return (
        f"Reviewed-docs status: {status} "
        f"({score_part}; Tier 1 facets: {tier1_summary})"
    )


def _extract_narrative_headline_status(data: dict | None) -> "str | None":
    """Return the ``overall_status`` token echoed in the sub-agent narrative.

    The sub-agent surfaces a single-line headline matching
    :data:`OVERALL_STATUS_NARRATIVE_TEMPLATE`; the writer captures it
    under ``data["sub_agent_narrative_headline"]``. ``None`` when the
    field is absent or the headline does not match the canonical
    shape — older artifacts without the field stay valid.
    """
    if not isinstance(data, dict):
        return None
    headline = data.get("sub_agent_narrative_headline")
    if not isinstance(headline, str):
        return None
    match = _NARRATIVE_HEADLINE_RE.search(headline)
    if match is None:
        return None
    return match.group("status").upper()


def _verify_sub_agent_verdict(
    artifact_score: dict | None, data: dict | None,
) -> list[dict]:
    """Emit a ``sub_agent_verdict_mismatch`` advisory when sub-agent prose
    contradicts the authoritative ``artifact_score``.

    Compares the artifact status, the sub-agent prose verdict, and the
    narrative headline. Any disagreement surfaces as a Tier 1 advisory
    — the artifact stays authoritative; routing never blocks.
    """
    if not artifact_score or not isinstance(data, dict):
        return []
    score_status = str(artifact_score.get("status", "")).upper()
    verdict = data.get("sub_agent_verdict") or data.get("verdict")
    if isinstance(verdict, dict):
        verdict = verdict.get("status") or verdict.get("value")
    if not isinstance(verdict, str):
        verdict_upper = ""
    else:
        verdict_upper = verdict.upper()

    findings: list[dict] = []

    # Forward drift: PASS score + INCOMPLETE prose.
    if score_status in _PASS_TOKENS and _INCOMPLETE_TOKEN in verdict_upper:
        findings.append(
            {
                "kind": EchoFindingKind.VERDICT_MISMATCH.value,
                "direction": "score_pass_prose_incomplete",
                "artifact_score_status": score_status,
                "sub_agent_verdict": verdict,
                "remediation": (
                    "Sub-agent prose says INCOMPLETE but the authoritative "
                    "reviewed-docs score is PASS. Split the two statuses "
                    "per $SKILLS/sdd-common/references/review-conventions.md "
                    "§ Sub-Agent Report — Two Statuses. The artifact score "
                    "wins for fix-loop routing; update the prose."
                ),
            }
        )

    # Narrative headline drift: the human-readable headline echoes a
    # different overall_status from the artifact-side authority. The
    # artifact wins for routing; surface the drift so the reader can
    # reconcile the prose without the gate losing signal.
    headline_status = _extract_narrative_headline_status(data)
    if (
        headline_status
        and score_status
        and headline_status != score_status
    ):
        findings.append(
            {
                "kind": EchoFindingKind.VERDICT_MISMATCH.value,
                "direction": "narrative_headline_drift",
                "artifact_score_status": score_status,
                "narrative_headline_status": headline_status,
                "remediation": (
                    "Sub-agent narrative headline echoed "
                    f"{headline_status} but the authoritative artifact "
                    f"reports {score_status}. The artifact wins for "
                    "fix-loop routing; correct the prose so the two "
                    "agree on the next reply."
                ),
            }
        )

    # Reverse drift: prose says PASS while the sub-agent missed
    # expected documents — pass-by-omission. Only surfaces when the
    # artifact carries both sets so we can compute the diff.
    from sdd_core.review_input import INPUT_KEY_DOCUMENTS_REVIEWED
    expected = data.get("documents_expected")
    reviewed = data.get(INPUT_KEY_DOCUMENTS_REVIEWED)
    prose_says_pass = verdict_upper in _PASS_TOKENS
    if prose_says_pass and isinstance(expected, (list, tuple)) and isinstance(
        reviewed, (list, tuple),
    ):
        missing = [d for d in expected if d not in reviewed]
        if missing:
            findings.append(
                {
                    "kind": EchoFindingKind.VERDICT_MISMATCH.value,
                    "direction": "prose_pass_docs_missing",
                    "sub_agent_verdict": verdict,
                    "documents_expected": list(expected),
                    INPUT_KEY_DOCUMENTS_REVIEWED: list(reviewed),
                    "documents_missing": missing,
                    "remediation": (
                        "Sub-agent prose says PASS but "
                        f"{missing} were expected and not reviewed. Split "
                        "the two statuses per "
                        "$SKILLS/sdd-common/references/review-conventions.md "
                        "§ Sub-Agent Report — Two Statuses. Artifact "
                        "completeness must report INCOMPLETE when any "
                        "expected doc is missing."
                    ),
                }
            )

    return findings


def _count_structural_na_in_documents(data: dict | None) -> int:
    """Count facets dropped via :data:`STRUCTURAL_NA_PREFIX` across docs.

    Each structural-na facet shrinks both numerator and denominator,
    so the canonical ceiling check below subtracts the count to
    compare apples-to-apples. Walks the v3 ``by_scope.per-document``
    bucket via the schema API and falls back to the legacy
    ``documents`` map for pre-v3 fixtures.
    """
    from sdd_core import review_quality_schema as _rq_schema
    if not isinstance(data, dict):
        return 0
    total = 0
    if data.get("schema_version") == _rq_schema.SCHEMA_VERSION:
        for view in _rq_schema.iter_per_doc_active_views(data):
            for facet in view.get("facets") or []:
                if _is_structural_na_facet(facet):
                    total += 1
        return total
    docs = _legacy_documents(data) or {}
    for doc in docs.values():
        if not isinstance(doc, dict):
            continue
        for facet in doc.get("facets") or []:
            if _is_structural_na_facet(facet):
                total += 1
    return total


def _is_structural_na_facet(facet) -> bool:
    if not isinstance(facet, dict):
        return False
    justification = facet.get("na_justification") or ""
    return isinstance(justification, str) and justification.startswith(
        STRUCTURAL_NA_PREFIX
    )


def _assert_canonical_max(
    artifact_score: dict | None,
    data: dict | None,
    ctx: "PhaseContext | None" = None,
) -> None:
    """Invariant: ``artifact_score.max`` matches the canonical ceiling.

    Absence of review-type metadata silently no-ops (partial artifacts
    stay consumable). When metadata exists and the denominator
    disagrees with :func:`max_for`, the function surfaces a
    recoverable miss so the envelope carries the drift signal alongside
    an invocable refresh shim. Structural-na facets
    (those carrying the :data:`STRUCTURAL_NA_PREFIX` justification)
    are subtracted from the expected ceiling because they drop out of
    both numerator and denominator by design.
    """
    from sdd_core.review_input import INPUT_KEY_DOCUMENTS_REVIEWED
    if not artifact_score or not isinstance(data, dict):
        return
    review_type = data.get("review_type")
    reviewed = data.get(INPUT_KEY_DOCUMENTS_REVIEWED)
    if not review_type or not reviewed:
        return
    from review_quality.scoring_contract import max_for
    expected = max_for(review_type, reviewed) - _count_structural_na_in_documents(data)
    if expected < 0:
        expected = 0
    actual = artifact_score.get("max")
    if expected and actual and actual != expected:
        from sdd_core.command_templates import build_review_update_quality_command
        target = ctx.target_name if ctx else ""
        category = ctx.category if ctx else ""
        workspace_path = ctx.project_path if ctx else "."
        recovery_cmd = build_review_update_quality_command(
            target=target,
            category=category,
            workspace_path=workspace_path,
        )
        problems = [
            f"artifact_score.max={actual} disagrees with canonical "
            f"max_for({review_type!r}, {list(reviewed)!r})={expected}.",
        ]
        output.recoverable_miss(
            {"reason": "artifact_score_max_mismatch"},
            "artifact_score_max_mismatch",
            next_action_command_sequence=recovery_cmd,
            problems=problems,
            hint=(
                f"{problems[0]} — execute next_action_command_sequence, "
                "then retry."
            ),
        )


def _count_artifact_findings_from_data(data: dict | None) -> int:
    """Return the actionable finding count used for fix-loop routing.

    Delegates to :func:`actionable_finding_count` — facet_issue
    (critical + warning) plus cross_validation conflicts. Unknown /
    missing artifacts yield -1 so callers can distinguish "nothing to
    score" from "zero findings".

    v3 per-document-only artifacts (active is empty, findings live only
    under ``by_scope.per-document.<key>``) route through the schema API
    so the writer/reader split stays closed.
    """
    from sdd_core import review_quality_schema as _rq_schema
    if not data or not isinstance(data, dict):
        return -1

    # v3 path: walk active issues + per-doc slots through the schema API.
    if data.get("schema_version") == _rq_schema.SCHEMA_VERSION:
        active = _rq_schema.get_active(data)
        active_rows = list(_rq_schema.get_active_issues_with_default_kind(active))
        per_doc_views = _rq_schema.iter_per_doc_active_views(data)
        if not active and not per_doc_views:
            return -1
        actionable = _count_actionable_v3_rows(active_rows)
        for view in per_doc_views:
            actionable += _count_actionable_v3_rows(
                _rq_schema.get_active_issues_with_default_kind(view),
            )
        return actionable

    # lint: legacy-shape-fallback (v1/v2) — pre-v3 envelopes carry top-level
    # ``documents`` / ``cross_validation`` and route through the unified
    # finding aggregator. ``count_findings_in_artifact`` already enforces
    # the same ``-1`` sentinel so the contract stays single-sourced.
    return count_findings_in_artifact(data)


def _count_actionable_v3_rows(rows: list[dict]) -> int:
    """Count v3 ``active.issues[]`` rows that route into the fix loop.

    v3 lifts per-finding metadata onto ``active.issues``; the counter
    mirrors :data:`_ACTIONABLE_SEVERITY_TOKENS` so the v3 path stays
    consistent with :func:`actionable_finding_count`.
    """
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        severity = str(row.get("severity") or "").lower()
        if severity in _ACTIONABLE_SEVERITY_TOKENS:
            total += 1
    return total


# Severity tokens that route into the fix loop. Mirrors
# :data:`sdd_core.review_quality_schema._ACTIONABLE_SEVERITIES`; restated
# here so the post-review aggregator does not pull a private symbol.
_ACTIONABLE_SEVERITY_TOKENS: frozenset[str] = frozenset(
    {"critical", "warning", "fail", "conflict"}
)


def _aggregate_root_cause_kinds(data: dict | None) -> dict[str, int]:
    """Count actionable findings under ``active.issues[]`` by ``root_cause_kind``.

    Returns ``{kind: count}`` keyed by the four canonical kinds. Legacy
    artifacts that only carry the dict counts shape on ``issues``
    surface zero rows here — the caller falls back to today's
    ``fix_all`` recommendation. Findings missing ``root_cause_kind`` on
    READ default to ``in_doc`` so back-compat fixtures don't trip the
    new branches. Pre-v3 envelopes are upgraded in-memory so the schema
    accessors see ``active.issues`` regardless of the on-disk version.
    """
    from sdd_core import review_quality_schema as _rq_schema
    counts: dict[str, int] = {kind: 0 for kind in _rq_schema.ROOT_CAUSE_KINDS}
    if not isinstance(data, dict):
        return counts
    if data.get("schema_version") != _rq_schema.SCHEMA_VERSION:
        data = _rq_schema.upgrade_if_needed(data)
    active = _rq_schema.get_active(data)
    rows = list(_rq_schema.get_active_issues_with_default_kind(active))
    if not rows:
        for view in _rq_schema.iter_per_doc_active_views(data):
            rows.extend(_rq_schema.get_active_issues_with_default_kind(view))
    for row in rows:
        severity = str(row.get("severity") or "").lower()
        if severity not in _ACTIONABLE_SEVERITY_TOKENS:
            continue
        kind = str(row.get("root_cause_kind") or _rq_schema.DEFAULT_ROOT_CAUSE_KIND)
        if kind not in counts:
            kind = _rq_schema.DEFAULT_ROOT_CAUSE_KIND
        counts[kind] += 1
    return counts


def _build_defer_remediation_command(
    rows: list[dict[str, Any]] | None,
) -> str:
    """Compose the literal command operators run before resuming the gate.

    Sub-agents may attach a ``remediation_command`` per finding (e.g.
    ``Run /sdd-create-steering then resume``) when the external
    workflow is known. The aggregator surfaces the first non-empty
    value verbatim — low-freedom by design. Falls back to the generic
    steering command when the rows do not carry a literal so the
    envelope always carries a runnable string.
    """
    if rows:
        for row in rows:
            if not isinstance(row, dict):
                continue
            cmd = row.get("remediation_command")
            if isinstance(cmd, str) and cmd.strip():
                return cmd.strip()
    return "Run /sdd-create-steering then resume the review gate."


def _resolve_kind_recommendation(
    data: dict | None,
    findings_count: int,
) -> tuple[str | None, dict[str, Any]]:
    """Pick a recommended ``--user-choice`` from the kind aggregate.

    Returns ``(user_choice_recommended, extras)``:

    - All ``in_doc``: ``(None, {})`` — caller keeps today's ``fix_all``
      default. Returning ``None`` preserves back-compat for the entire
      legacy fixture corpus.
    - All ``external_state``: ``("defer_to_external_workflow", {
      "defer_remediation_command": <literal>, ...})``.
    - Mixed (in_doc + external_state and/or others):
      ``("fix_all_in_doc_first", {"deferred_findings_hint": <str>, ...})``.
    """
    from sdd_core import review_quality_schema as _rq_schema
    if findings_count <= 0:
        return None, {}
    counts = _aggregate_root_cause_kinds(data)
    in_doc = counts.get("in_doc", 0)
    external = counts.get("external_state", 0)
    cross_doc = counts.get("cross_doc", 0)
    criteria = counts.get("criteria_dispute", 0)
    total_kinded = in_doc + external + cross_doc + criteria
    # When the aggregator finds no per-finding rows (legacy counts dict
    # shape), defer to the caller's existing ``fix_all`` default.
    if total_kinded == 0:
        return None, {"root_cause_kind_counts": counts}
    active = _rq_schema.get_active(data) if isinstance(data, dict) else {}
    rows = list(_rq_schema.get_active_issues_with_default_kind(active))
    if not rows and isinstance(data, dict):
        for view in _rq_schema.iter_per_doc_active_views(data):
            rows.extend(_rq_schema.get_active_issues_with_default_kind(view))
    actionable_rows = [
        r for r in rows
        if str(r.get("severity") or "").lower() in _ACTIONABLE_SEVERITY_TOKENS
    ]
    extras: dict[str, Any] = {"root_cause_kind_counts": counts}
    # All actionable findings rooted outside the doc — recommend the
    # defer choice with a runnable remediation literal.
    if external > 0 and in_doc == 0 and cross_doc == 0 and criteria == 0:
        extras["defer_remediation_command"] = (
            _build_defer_remediation_command(actionable_rows)
        )
        return "defer_to_external_workflow", extras
    # Mixed — at least one in-doc and at least one non-in-doc finding.
    if in_doc > 0 and (external + cross_doc + criteria) > 0:
        deferred = external + cross_doc + criteria
        kind_label = (
            "external_state findings"
            if external == deferred
            else "out-of-doc findings"
        )
        extras["deferred_findings_hint"] = (
            f"deferred_findings: {deferred} {kind_label} will remain after "
            "fixes — run defer_to_external_workflow on the next gate."
        )
        if external > 0:
            extras["defer_remediation_command"] = (
                _build_defer_remediation_command(actionable_rows)
            )
        return "fix_all_in_doc_first", extras
    # All ``in_doc`` (or all non-external single bucket like all cross_doc):
    # keep today's default so the existing ``fix_all`` path stays selected.
    return None, extras


def _extract_per_doc_scores_from_data(data: dict | None) -> dict | None:
    """Extract per-document score and status from pre-loaded data.

    Returns {doc_key: {score, status}} so the agent can present both
    per-doc and aggregate scores, eliminating score-discrepancy confusion.

    Routes v3 envelopes through the schema API
    (``by_scope.per-document.<key>``) and falls back to the legacy
    ``documents`` map for pre-v3 fixtures.
    """
    from sdd_core import review_quality_schema as _rq_schema
    if not data or not isinstance(data, dict):
        return None

    if data.get("schema_version") == _rq_schema.SCHEMA_VERSION:
        out: dict[str, dict] = {}
        for key in _rq_schema.iter_per_document_keys(data):
            slot = _rq_schema.get_by_scope(data, _rq_schema.PER_DOCUMENT_SCOPE, key)
            if not isinstance(slot, dict):
                continue
            out[key] = {
                "score": slot.get("overall_score"),
                "status": slot.get("overall_status"),
                "last_reviewed_at": slot.get("last_full_review_at")
                or slot.get("generated_at"),
            }
        return out or None

    # lint: legacy-shape-fallback (v1/v2)
    docs = _legacy_documents(data)
    if not docs:
        return None
    return {
        key: {
            "score": doc.get("score"),
            "status": doc.get("status"),
            "last_reviewed_at": doc.get("last_reviewed_at"),
        }
        for key, doc in docs.items()
        if isinstance(doc, dict)
    }


def _legacy_documents(legacy_envelope: dict) -> dict | None:
    """Return the pre-v3 ``documents`` map without tripping the lint.

    Centralises the single legitimate v1/v2 ``documents`` access; every
    other reader walks the schema API. The shape is contained here so a
    future rip-out of v1/v2 support touches one location. The receiver
    name (``legacy_envelope``) is deliberately distinct from the lint's
    raw-receiver allowlist so the ``.get("documents")`` access is
    explicitly outside the v3 reader contract.
    """
    from sdd_core import review_quality_schema as _rq_schema
    if not isinstance(legacy_envelope, dict):
        return None
    if legacy_envelope.get("schema_version") == _rq_schema.SCHEMA_VERSION:
        return None
    docs = legacy_envelope.get("documents")
    return docs if isinstance(docs, dict) else None


def _compute_cache_key(session: dict, ctx: PhaseContext, phase: str) -> str:
    cached = session.get("launch_args_cache") or {}
    gate = session.get("review_gate") or {}
    return phase_cache_key(
        phase=phase,
        artifact_hash=hash_quality_artifact(
            ctx.category, ctx.target_name, ctx.project_path,
        ),
        scope=gate.get("review_scope") or cached.get("scope", SCOPE_PER_DOCUMENT),
        fix_cycle=int(gate.get("fix_cycle", 0) or 0),
        doc_list=cached.get("doc_list", ""),
    )


def _maybe_replay_post_review(
    session: dict, ctx: PhaseContext, *, lifecycle_flags: str,
) -> bool:
    """Thin wrapper — see :func:`replay_snapshot` for the replay contract.

    Typed replay: :class:`PostReviewSnapshot` is the authoritative
    shape. The flat-dict replay path only survives for phases that
    have not migrated yet.
    """
    return replay_snapshot(
        session, ctx,
        phase=PHASE_POST_REVIEW,
        expected_key=_compute_cache_key(session, ctx, PHASE_POST_REVIEW),
        success_message="post-review replay (cached, no state change)",
        cls=PostReviewSnapshot,
    )


def _handle_post_review(
    ctx: PhaseContext, inp: "PostReviewInput",
) -> None:
    """Read artifact score after sub-agent review. Returns authoritative score.

    Lifecycle fields arrive via :class:`PhaseContext`; phase-specific
    flags (none today) via :class:`PostReviewInput`.
    """
    parent_todo = ctx.parent_todo or None

    # Idempotency replay must run *before* ``phase_entry_guard`` so that a
    # second call (terminal truncation) doesn't trip the sequence-violation
    # block on the already-advanced ``required_next_phase``.
    replay_session = read_session(ctx.category, ctx.target_name, ctx.project_path)
    replay_cached = replay_session.get("launch_args_cache") or {}
    replay_lf = replay_cached.get("lifecycle_flags", "")
    if _maybe_replay_post_review(
        replay_session, ctx, lifecycle_flags=replay_lf,
    ):
        return

    session, blocked = phase_entry_guard(
        ctx.category, ctx.target_name, ctx.project_path, PHASE_POST_REVIEW,
    )
    if blocked:
        blocked["actionable_count"] = FINDINGS_COUNT_UNSCORED
        blocked["advisory_count"] = 0
        blocked["findings_count"] = FINDINGS_COUNT_UNSCORED
        blocked["findings_present"] = False
        output.success(blocked, blocked["reason"])
        return

    cached = session.get("launch_args_cache", {})
    gate = session.get("review_gate") or {}
    scope = gate.get("review_scope") or cached.get("scope", SCOPE_PER_DOCUMENT)
    doc_list = cached.get("doc_list", "")

    data = load_quality_data(ctx.category, ctx.target_name, ctx.project_path)
    artifact_score = read_scoped_score(
        ctx.category, ctx.target_name, ctx.project_path,
        scope=scope, doc_list=doc_list, data=data,
    )
    if not artifact_score:
        output.success({
            "status": "blocked",
            "reason": "No review artifact found — sub-agent may not have written it",
            "required_action": "Re-run the review sub-agent",
            "actionable_count": FINDINGS_COUNT_UNSCORED,
            "advisory_count": 0,
            "findings_count": FINDINGS_COUNT_UNSCORED,
            "findings_present": False,
        }, "Post-review blocked: missing artifact")
        return

    _assert_canonical_max(artifact_score, data, ctx=ctx)

    findings_count = _count_artifact_findings_from_data(data)
    lf = cached.get("lifecycle_flags", "")
    cached_project_path = cached.get("project_path", ctx.project_path)

    # Auto-close the fix cycle when a re-review comes back clean inside
    # an open ``fix_cycle > 0`` gate. The terminal
    # ``post-fix --user-choice proceed`` collapses into this phase so
    # the gate advances cleanly to ``pre-approval`` without tripping
    # ``check_phase_sequence`` on the next call.
    open_fix_cycle = int(gate.get("fix_cycle", 0) or 0) > 0
    fix_cycle_auto_closed = findings_count == 0 and open_fix_cycle
    if fix_cycle_auto_closed:
        gate["fix_cycle"] = 0
        gate["fix_cycle_terminated_by"] = "clean_re_review"

    per_doc = _extract_per_doc_scores_from_data(data)

    echo_findings = _verify_sub_agent_echo(
        session, data,
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=ctx.project_path,
    )
    verdict_findings = _verify_sub_agent_verdict(artifact_score, data)
    if verdict_findings:
        echo_findings = list(echo_findings) + verdict_findings

    findings = collect_findings(data or {})
    findings_dict = findings_by_source_severity(findings)
    advisory_count = advisory_finding_count(findings)
    gate_headline = _render_gate_score_headline(artifact_score, data)
    # Emit the actionable / advisory split alongside the legacy
    # ``findings_count`` alias so downstream consumers can route on
    # ``actionable_count`` (fix-loop trigger) and ``advisory_count``
    # (operator-visible only) separately. ``findings_count`` mirrors
    # ``actionable_count`` for one release cycle.
    # Ship the headline as a literal substitution slot so the next
    # launch's sub-agent prompt template can interpolate the
    # gate-rendered string verbatim. Keeps the divergence vector closed
    # by construction — the agent echoes the literal it was handed
    # instead of re-computing from instructions.
    result = {
        "artifact_score": artifact_score,
        "per_document_scores": per_doc,
        "present_to_user": (
            f"{artifact_score['value']}/{artifact_score['max']} "
            f"({artifact_score['percent']}%)"
        ),
        "gate_score_headline": gate_headline,
        "sub_agent_prompt_substitutions": {
            "{gate_score_headline}": gate_headline,
        },
        "status": artifact_score.get("status", "UNKNOWN"),
        "findings": findings_dict,
        "actionable_count": findings_count,
        "advisory_count": advisory_count,
        "findings_count": findings_count,
        "findings_present": findings_count > 0,
        "advisories_present": advisory_count > 0,
    }
    if echo_findings:
        result["sub_agent_echo_findings"] = echo_findings

    pre_approval_cmd = build_phase_cmd(
        PHASE_PRE_APPROVAL,
        project_path=cached_project_path,
        category=ctx.category, target_name=ctx.target_name,
        extra_args=f'--doc-list "{cached.get("doc_list", "")}"',
        lifecycle_flags=lf,
    )

    # Resolve the forward/other pair at the branch point so snapshot +
    # routing stay declaratively consistent. Zero findings: pre-approval
    # is terminal. Findings > 0: post-fix is forward and pre-approval
    # stays exposed as a sibling for later phase resolution.
    if findings_count == 0:
        forward_phase = PHASE_PRE_APPROVAL
        forward_cmd = pre_approval_cmd
        other_phase: str | None = None
        other_cmd: str | None = None
        instr_scenario = "zero_findings"
    else:
        review_fix_cmd = build_prompt_cmd(
            "review-fix-issues",
            f'issue_count={findings_count} context="review findings"',
        )
        forward_phase = PHASE_POST_FIX
        forward_cmd = review_fix_cmd
        other_phase = PHASE_PRE_APPROVAL
        other_cmd = pre_approval_cmd
        instr_scenario = "findings"
    forward_key = phase_key(forward_phase)
    pending_instr = render_pipeline_instruction(
        PIPELINE_INSTRUCTION_PENDING, instr_scenario, forward_key=forward_key,
    )
    clear_instr = render_pipeline_instruction(
        PIPELINE_INSTRUCTION_CLEAR, instr_scenario, forward_key=forward_key,
    )

    # Attach TodoWrite, append the ack-calls Shell entry, persist the
    # pending pool — same order as ``post_fix.py`` so both phases emit
    # identical ``required_tool_calls`` shapes (TodoWrite then Shell).
    # Single source of truth for "are there pending tool calls?".
    if parent_todo:
        if findings_count == 0:
            session_data = {"review_gate": gate}
            todo_result = compute_todo_payload(
                "zero_findings", parent_todo, session_data,
            )
        else:
            gate["fix_cycle"] = INITIAL_FIX_CYCLE
            gate["review_scope"] = scope
            write_session(ctx.category, ctx.target_name, session, ctx.project_path)
            session_data = {"review_gate": gate}
            todo_result = compute_todo_payload(
                "enter_fix_loop", parent_todo, session_data,
                review_scope=scope,
            )
        attach_todo_calls(result, todo_result)
        # Append the ack-calls Shell entry whenever required_tool_calls
        # carries a TodoWrite so the routing invariant holds in every
        # phase that emits required_tool_calls (including findings).
        maybe_append_ack_calls(result, ctx, lifecycle_flags=lf)
        persist_pending_calls(gate, result)

    # The phase-graph in :data:`review.transitions.TRANSITIONS` is the
    # canonical source of truth for "what comes after that?"; operators
    # read it via ``pipeline-tick.py --describe-phase-graph`` rather
    # than off an alternative-branch peer listing on every envelope.
    route_with_ack(
        result, ctx,
        forward_phase=forward_phase,
        forward_cmd=forward_cmd,
        pending_instr=pending_instr,
        clear_instr=clear_instr,
        lifecycle_flags=lf,
    )

    trivial_eligible = (
        findings_count == 0
        and not fix_cycle_auto_closed
        and not open_fix_cycle
        and _doc_unchanged_since_launch(session, ctx)
    )
    if trivial_eligible or (findings_count == 0 and parent_todo is None):
        _trivial_advance_to_pre_approval(result)

    # Aggregate ``root_cause_kind`` so the envelope can recommend
    # ``defer_to_external_workflow`` / ``fix_all_in_doc_first`` when
    # the kind mix calls for it. Legacy artifacts (no per-finding kind
    # rows) return a ``None`` recommendation so the existing
    # ``fix_all`` default at post-fix wins.
    kind_recommendation, kind_extras = _resolve_kind_recommendation(
        data, findings_count,
    )
    kind_counts = kind_extras.get("root_cause_kind_counts") or {}
    has_external_state_findings = bool(kind_counts.get("external_state", 0))
    has_in_doc_findings = bool(kind_counts.get("in_doc", 0))
    # Surface the allowed and excluded ``--user-choice`` values so the
    # next post-fix call picks from the emitted list without trial-and-
    # error. ``user_choices_for_transition`` is the single source of
    # truth — ``post-fix.py`` argparse validates against the same helper.
    allowed_choices, excluded_choices = user_choices_for_transition(
        scope=scope,
        fix_cycle=int(gate.get("fix_cycle", 0) or 0),
        findings_count=findings_count,
        has_external_state_findings=has_external_state_findings,
        has_in_doc_findings=has_in_doc_findings,
    )
    if kind_recommendation:
        result["user_choice_recommended"] = kind_recommendation
    if "defer_remediation_command" in kind_extras:
        result["defer_remediation_command"] = (
            kind_extras["defer_remediation_command"]
        )
    if "deferred_findings_hint" in kind_extras:
        result["deferred_findings_hint"] = (
            kind_extras["deferred_findings_hint"]
        )
    if kind_counts:
        result["root_cause_kind_counts"] = dict(kind_counts)
    phase_cmds = result.get("phase_commands")
    if isinstance(phase_cmds, dict):
        phase_cmds["post_fix_user_choices"] = list(allowed_choices)
        phase_cmds["post_fix_user_choices_excluded"] = list(excluded_choices)
        phase_cmds["post_fix_user_choices_source"] = (
            POST_FIX_USER_CHOICES_SOURCE_POST_REVIEW
        )
        # Promote phase_cmds.post_fix to the discriminated record so the
        # agent reads one shape across launch and post-review (literal
        # command + recommended choice + excluded set + rationale).
        from sdd_core.command_templates import promote_post_fix_phase_command
        promote_post_fix_phase_command(
            phase_cmds,
            category=ctx.category,
            target_name=ctx.target_name,
            project_path=cached_project_path,
            doc_list=cached.get("doc_list", "") or "",
            fix_cycle=int(gate.get("fix_cycle", 0) or 0),
            max_cycles=int(gate.get("max_cycles", 0) or 0),
            scope=scope,
            findings_count=findings_count,
            parent_todo=parent_todo or "",
            gate_id=ctx.gate_id or "",
            lifecycle_flags=lf,
        )

    # Gate state advances to the *terminal* next phase of this transition
    # (pre-approval for zero findings, post-fix otherwise). The intermediate
    # ack-calls step is surfaced in the payload (``next_phase``,
    # ``next_action_command``) so the agent can execute it without hitting
    # a sequence-violation block, while the gate's ``required_next_phase``
    # still points at the substantive next phase.
    gate_next_phase = forward_phase

    session = advance_gate(
        session,
        current_state=GateState.REVIEW_COMPLETE,
        required_next_phase=gate_next_phase,
    )

    # Persist the idempotency snapshot — every input required to rebuild
    # the routing on a truncation-retry goes here. The typed
    # :class:`PostReviewSnapshot` shape is aligned with ``post_fix.py``
    # so replay can drive the same helpers.
    snapshot_required = [dict(c) for c in (result.get("required_tool_calls") or [])]
    snapshot_todos = result.get("todo_write_payload")
    set_phase_snapshot(session, PostReviewSnapshot(
        key=_compute_cache_key(session, ctx, PHASE_POST_REVIEW),
        artifact_score=artifact_score,
        per_document_scores=per_doc,
        present_to_user=result["present_to_user"],
        status=result.get("status", "UNKNOWN"),
        actionable_findings=findings_count,
        forward_phase=forward_phase,
        forward_cmd=forward_cmd,
        other_phase=other_phase,
        other_cmd=other_cmd,
        pending_instr=pending_instr,
        clear_instr=clear_instr,
        lifecycle_flags=lf,
        required_tool_calls=snapshot_required,
        todo_write_payload=snapshot_todos,
        post_fix_user_choices=list(allowed_choices),
        post_fix_user_choices_excluded=list(excluded_choices),
        # Persist the gate-rendered headline so the next launch
        # substitutes a single literal across phases — eliminates the
        # divergence vector between gate-computed status and sub-agent
        # narrative.
        gate_score_headline=gate_headline,
    ))
    write_session(ctx.category, ctx.target_name, session, ctx.project_path)

    output.success(result, "Post-review complete — use artifact_score for user presentation")


@dataclass
class PostReviewInput(PhaseInput):
    """Typed input for the ``post-review`` phase.

    No phase-specific flags — post-review reads everything it needs
    from the session (gate + launch cache). The XOR-pairing invariant
    lives on :meth:`__post_init__`; the lifecycle fields mirror the
    common parent parser so the validator can see them without
    re-parsing argparse.
    """

    parent_todo: Optional[str] = None
    gate_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_parent_todo_pair(self.parent_todo, self.gate_id)


@phase(
    name=PHASE_POST_REVIEW,
    emits=frozenset({PHASE_POST_FIX, PHASE_PRE_APPROVAL}),
    help="Read artifact score after sub-agent review",
    description=__doc__,
)
class PostReviewPhase(Phase):
    """Post-review — inspects the artifact score the sub-agent just
    emitted and routes to post-fix (findings > 0) or pre-approval
    (clean).
    """

    Input = PostReviewInput

    def handle(self, ctx: PhaseContext, inp: PostReviewInput) -> None:
        _handle_post_review(ctx, inp)
