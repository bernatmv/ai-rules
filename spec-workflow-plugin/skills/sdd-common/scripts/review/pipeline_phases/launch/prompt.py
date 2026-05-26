"""Prompt-building helpers for the launch phase.

Owns the gate-prompt pre-render, doc-list / prompt SHA computation,
``prompt_change_status`` classifier, ``{gate_score_headline}`` literal
substitution, and the sub-agent prompt assembly. Constants for the
three-state ``prompt_change_status`` vocabulary and prompt-redaction
key set live here so phase-handlers and tests have a single source of
truth.
"""
from __future__ import annotations

import hashlib
import os

from sdd_core.prompts import (
    SUB_AGENT_ECHO_INSTRUCTION,
    build_sub_agent_echo_instruction,
    substitute_sub_agent_echo_placeholders,
)
from review_quality.gate_session import (
    GATE_LAUNCH_ARGS_CACHE,
    read_session,
)

from ...phase_kit import PhaseContext
from .. import SUB_AGENT_BOUNDARY
from ..prompt_builder import build_doc_review_prompt
from ..resolvers import resolve_prd_file_path


# Block-first envelope keys redacted from agent-facing responses while
# preconditions are unmet — without the prompt the agent has no SHA to
# dispatch off.
_PROMPT_REDACT_KEYS: tuple[str, ...] = (
    "sub_agent_prompt",
    "sub_agent_prompt_sha256",
    "sub_agent_prompt_sha256_note",
)

# Three-state vocabulary surfaced as ``prompt_change_status`` on every
# launch envelope after the first. Single source of truth so phase
# handlers and tests don't drift on the literal string set.
# Stable token: prior + current SHAs match — no re-dispatch needed.
PROMPT_CHANGE_UNCHANGED = "unchanged"
# Stable token: doc body shifted between launches — sub-agent must re-run.
PROMPT_CHANGE_DOC_CHANGED = "doc_changed"
# Stable token: prompt template shifted — forces fresh dispatch even on unchanged docs.
PROMPT_CHANGE_PROMPT_CHANGED = "prompt_changed"

# ``launch_args_cache`` keys carrying the prior-launch hashes so a
# re-launch can detect whether the user edited the doc or whether the
# prompt template itself shifted.
# Cache key: SHA of last-launched sub-agent prompt; drives prompt-drift detection.
_CACHE_LAST_PROMPT_SHA = "last_prompt_sha"
# Cache key: SHA of last-launched doc bundle; drives doc-drift detection.
_CACHE_LAST_DOC_SHA = "last_doc_sha"

# Launch-envelope key that surfaces the gate prompt's pre-rendered
# spec + adapter payload so agents do not re-invoke
# ``util/generate-prompt.py`` at the post-review fix-decision boundary.
GATE_PROMPT_KEY = "gate_prompt"
# Prompt-registry id pre-rendered into ``gate_prompt`` for launch
# envelopes — the fix-decision the agent surfaces to the user once
# post-review reports findings.
_GATE_PROMPT_TYPE = "review-fix-issues"


# Static checklist embedded in launch envelopes so agents track the mandatory phase ordering.
_PROGRESS_CHECKLIST = (
    "## Review Gate Checklist\n"
    "\n"
    "- [ ] Run review sub-agent\n"
    "- [ ] Run post-review phase (MANDATORY — gets authoritative score)\n"
    "- [ ] Present findings to user (fix-decision gate)\n"
    "- [ ] Apply fixes (if needed)\n"
    "- [ ] Run post-fix phase (MANDATORY)\n"
    "- [ ] Apply `todo_write_payload` via TodoWrite\n"
    "- [ ] Run pre-approval phase (MANDATORY)\n"
    "\n"
    "Copy this checklist into your notes to track progress.\n"
    "Phase commands are MANDATORY — do NOT call underlying scripts directly."
)

# Versioned key for :data:`_PROGRESS_CHECKLIST` so consumers can detect
# checklist edits (bump the ``vN`` suffix whenever the MANDATORY-line
# count or ordering changes).
PROGRESS_CHECKLIST_KEY = "review-gate.default.v1"


def canonicalise_sub_agent_prompt(prompt: str) -> str:
    """Strip trailing whitespace per line so hash is resilient to
    rendering differences (CRLF, trailing spaces) that Opus 4.7 may
    normalise on its own when echoing the prompt back."""
    lines = (prompt or "").splitlines()
    return "\n".join(line.rstrip() for line in lines)


def sub_agent_prompt_sha256(prompt: str) -> str:
    canonical = canonicalise_sub_agent_prompt(prompt)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _compute_doc_list_sha(
    *, category: str, target_name: str, project_path: str, doc_list: str,
) -> str:
    """Hash on-disk contents of every doc in *doc_list* (sorted, byte-stable).

    Missing files contribute an empty body so a re-launch with the same
    missing set produces the same digest. Used to disambiguate
    ``prompt_change_status`` between ``doc_changed`` and ``unchanged``.
    """
    from sdd_core.paths import doc_dir_path
    h = hashlib.sha256()
    doc_directory = doc_dir_path(category, target_name, project_path)
    for doc in sorted(d.strip() for d in (doc_list or "").split(",") if d.strip()):
        path = os.path.join(doc_directory, doc)
        h.update(doc.encode("utf-8"))
        h.update(b"\x00")
        try:
            with open(path, "rb") as f:
                h.update(f.read())
        except (FileNotFoundError, OSError, IsADirectoryError):
            pass
        h.update(b"\xff")
    return h.hexdigest()


def _read_prior_launch_shas(
    *, category: str, target_name: str, project_path: str,
) -> tuple[str, str]:
    """Return ``(prior_prompt_sha, prior_doc_sha)`` from the persisted session.

    Returns ``("", "")`` when no session file exists or the cache has
    not yet been seeded (first launch in a workflow).
    """
    from review_quality.gate_session import session_path as _session_path
    if not os.path.isfile(_session_path(category, target_name, project_path)):
        return "", ""
    session = read_session(category, target_name, project_path)
    cache = session.get(GATE_LAUNCH_ARGS_CACHE) or {}
    return (
        str(cache.get(_CACHE_LAST_PROMPT_SHA) or ""),
        str(cache.get(_CACHE_LAST_DOC_SHA) or ""),
    )


def _classify_prompt_change(
    *, prior_prompt_sha: str, prior_doc_sha: str,
    curr_prompt_sha: str, curr_doc_sha: str,
) -> str | None:
    """Three-state classifier for the ``prompt_change_status`` field.

    Returns ``None`` on the first launch (no prior values to compare so
    the field is omitted). Prompt drift wins over doc drift because a
    template edit forces a fresh sub-agent dispatch even when the doc
    is unchanged.
    """
    if not prior_prompt_sha and not prior_doc_sha:
        return None
    if prior_prompt_sha != curr_prompt_sha:
        return PROMPT_CHANGE_PROMPT_CHANGED
    if prior_doc_sha != curr_doc_sha:
        return PROMPT_CHANGE_DOC_CHANGED
    return PROMPT_CHANGE_UNCHANGED


def _build_gate_prompt() -> dict | None:
    """Pre-render the post-review fix-decision prompt for the launch envelope.

    Returns a dict containing the un-rendered :class:`PromptSpec` (so
    consumers can verify integrity), the active-adapter-rendered
    payload (so the agent uses :tool:`AskUserQuestion` directly without
    re-invoking ``util/generate-prompt.py``), the prompt-registry id,
    and a ``registry_sha256`` for drift detection. Returns ``None`` if
    the prompt-registry entry isn't eligible for structured rendering
    (the agent falls back to the markdown path through
    ``prompt_commands.review_fix_issues``).
    """
    import dataclasses
    from sdd_core.prompts import (
        load_registry,
        registry_entry_sha256,
        render_prompt_for_envelope,
        render_prompt_for_harness,
    )
    placeholder_params = {
        "issue_count": "{issue_count}",
        "context": "{review_context}",
    }
    try:
        spec = render_prompt_for_envelope(
            _GATE_PROMPT_TYPE, placeholder_params,
        )
    except (KeyError, ValueError):
        return None
    if spec is None:
        return None
    # ``render_prompt_for_harness`` resolves the active adapter; failure
    # is non-fatal for ``gate_prompt`` (the agent falls back to the
    # spec-only view when no adapter is wired). ``SystemExit`` covers
    # ``output.error``-style aborts inside the loader.
    try:
        payload = render_prompt_for_harness(
            _GATE_PROMPT_TYPE, placeholder_params,
        )
    except (KeyError, ValueError, SystemExit):
        payload = None
    except Exception:  # pragma: no cover — adapter loader is best-effort
        payload = None
    try:
        registry_sha = registry_entry_sha256(_GATE_PROMPT_TYPE)
    except (KeyError, FileNotFoundError):
        registry_sha = ""
    return {
        "prompt_type": _GATE_PROMPT_TYPE,
        "spec": dataclasses.asdict(spec),
        "payload": payload,
        "registry_sha256": registry_sha,
    }


def _resolve_headline_from_artifact(
    *, category: str, target_name: str, project_path: str,
) -> str:
    """Render a gate headline directly from the canonical artifact's ``active``.

    Used when the post-review snapshot is unavailable (cleared session,
    fresh launch after a complete) but a prior verdict still lives on
    ``review-quality.json``. Returns an empty string when the artifact
    is missing or carries no overall_score / overall_status to render.
    """
    from . import phase as _phase  # noqa: F401  ensure parent package init
    from .. import load_quality_data
    from ..post_review import _render_gate_score_headline
    from sdd_core import review_quality_schema as _rq_schema

    data = load_quality_data(category, target_name, project_path)
    if not isinstance(data, dict):
        return ""
    # Upgrade in-memory so the v3 ``active`` block carries the headline
    # source for both canonical and legacy v1/v2 artifacts. The schema
    # upgrader hoists pre-v3 top-level ``overall_score`` /
    # ``overall_status`` onto ``active`` losslessly.
    data = _rq_schema.upgrade_if_needed(data)
    active = _rq_schema.get_active(data)
    overall_score = active.get("overall_score")
    overall_status = active.get("overall_status")
    if not overall_score and not overall_status:
        return ""
    artifact_score = None
    if isinstance(overall_score, dict):
        artifact_score = {
            "value": overall_score.get("value", 0),
            "max": overall_score.get("max", 0),
            "percent": overall_score.get("percent"),
            "status": overall_status or "UNKNOWN",
        }
    elif overall_status:
        artifact_score = {
            "value": 0, "max": 0, "percent": None,
            "status": overall_status,
        }
    headline_data = active if active else data
    return _render_gate_score_headline(artifact_score, headline_data)


def _apply_post_review_substitutions(
    prompt: str, *, category: str, target_name: str, project_path: str,
) -> str:
    """Return *prompt* with gate-score-headline substitutions applied.

    Substitution sources, in order: the prior :class:`PostReviewSnapshot`
    (carries the literal the gate already rendered), then the canonical
    ``review-quality.json`` ``active`` block (any persisted verdict
    re-renders the headline). The placeholder remains in *prompt* only
    when neither source carries a verdict (first launch with no prior
    review). Function-scope imports avoid a module-load cycle with
    :mod:`review.snapshots`.
    """
    if "{gate_score_headline}" not in prompt:
        return prompt
    from review.snapshots import PostReviewSnapshot
    from review_quality.gate_session import (
        get_phase_snapshot, read_session,
    )
    try:
        session = read_session(category, target_name, project_path)
    except Exception:  # pragma: no cover - defensive: fresh project, no session
        session = None
    snap = None
    if session is not None:
        snap = get_phase_snapshot(
            session, "post-review", cls=PostReviewSnapshot,
        )
    headline = getattr(snap, "gate_score_headline", "") if snap else ""
    if not headline:
        headline = _resolve_headline_from_artifact(
            category=category,
            target_name=target_name,
            project_path=project_path,
        )
    if not headline:
        return prompt
    return prompt.replace("{gate_score_headline}", headline)


def _build_sub_agent_prompt(
    review_skill: str, ctx: PhaseContext, doc_list: str, review_type: str,
    assessment_staging_path: str, scope: str | None = None,
) -> tuple[str, str, str]:
    """Build the sub-agent prompt and staging instruction injection.

    Applies the ``{gate_score_headline}`` literal substitution when a
    prior :class:`PostReviewSnapshot` carries one. The gate renders the
    headline once at post-review emit time; the next launch's prompt
    embeds that literal so the sub-agent echoes the gate's verdict
    instead of recomputing it.
    """
    prd_file_path = None
    if ctx.category == "discovery":
        prd_file_path = resolve_prd_file_path(ctx.target_name, ctx.project_path)

    sub_agent_prompt, review_skill_path, verification_file = build_doc_review_prompt(
        review_skill, ctx.target_name, ctx.project_path, doc_list, ctx.category,
        review_type=review_type, prd_file_path=prd_file_path, scope=scope,
    )

    sub_agent_prompt = _apply_post_review_substitutions(
        sub_agent_prompt,
        category=ctx.category,
        target_name=ctx.target_name,
        project_path=ctx.project_path,
    )

    from sdd_core.command_templates import build_update_quality_command
    update_quality_cmd = build_update_quality_command(
        review_type=review_type,
        scope=scope,
        staging_path=assessment_staging_path,
    ).render()
    staging_instruction = (
        f"\n\nAssessment staging: Write intermediate assessment JSON to "
        f"`{assessment_staging_path}` (NOT /tmp/). "
        f"Then pass this path to `{update_quality_cmd}`."
    )
    sub_agent_prompt = sub_agent_prompt.replace(
        SUB_AGENT_BOUNDARY,
        staging_instruction + SUB_AGENT_BOUNDARY,
    )
    return sub_agent_prompt, review_skill_path, verification_file
