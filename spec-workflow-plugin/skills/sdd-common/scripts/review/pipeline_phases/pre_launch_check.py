"""Pipeline pre-launch-check phase.

Post-write validator hook that runs the same dispatch as
``launch``'s requirements antipattern pre-check but **never advances
gate state**. Agents call this between ``StrReplace`` edits to validate
bundled fixes before committing to ``--phase launch``.

Design notes (see ``docs/sdd-create-spec-*-implementation-plan.md``):
  * Idempotent by construction — reads no session state, writes no
    session state.
  * Returns structured findings + persisted plan-file path so agents can
    diff successive runs (plan-validate-execute pattern).
  * SRP — delegates validator invocation to ``sdd_core.pre_check``; the
    phase handler only shapes the response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from sdd_core import cli, output
from sdd_core import paths as _paths
from sdd_core.command_templates import (
    build_pre_launch_check_command,
    build_template_resolve_commands,
)
from sdd_core.pre_check import (
    OUTCOME_LINT_FAILED,
    OUTCOME_NOT_YET_AUTHORED,
    OUTCOME_PASS,
    OUTCOME_VALIDATOR_NOT_REGISTERED,
    build_authoring_guardrails,
    build_pre_launch_payload,
    run_precheck,
    should_run_precheck,
)
from sdd_core.paths import pre_launch_findings_path

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase


# Versioned checklist key for the pre-launch-check phase. Mirrors
# ``PROGRESS_CHECKLIST_KEY`` from launch.py so consumers can pin a TodoWrite
# list to a known revision and detect copy edits.
PRE_LAUNCH_CHECKLIST_KEY = "pre-launch.v1"

# Maximum identical-finding iterations before the handler emits a
# ``repeat_detected`` escalation marker. Three is enough to cover a
# normal "diagnose -> fix -> verify" loop while bounding the cost of a
# stuck agent.
_REPEAT_LIMIT = 3


def _format_pass(counts: dict, doc: str) -> str:
    return (
        f"pre-launch-check: PASS — "
        f"{counts['errors']} error(s), "
        f"{counts['warnings']} warning(s)"
    )


def _format_not_yet_authored(counts: dict, doc: str) -> str:
    if doc:
        return f"pre-launch-check: not yet authored — write {doc} first"
    return "pre-launch-check: not yet authored — write doc first"


def _format_lint_failed(counts: dict, doc: str) -> str:
    return (
        f"pre-launch-check: FAIL — "
        f"{counts['errors']} error(s), "
        f"{counts['warnings']} warning(s)"
    )


_OUTCOME_MESSAGE_BUILDERS: dict[str, Callable[[dict, str], str]] = {
    OUTCOME_PASS: _format_pass,
    OUTCOME_NOT_YET_AUTHORED: _format_not_yet_authored,
    OUTCOME_LINT_FAILED: _format_lint_failed,
}


# Self-description of the agent-stable response envelope. Surfaced by
# the ``--describe-envelope`` flag so agents can read the outcome enum
# off the script instead of memorising it from prose.
_ENVELOPE_DESCRIPTION: dict = {
    "phase": "pre-launch-check",
    "fields": [
        {"name": "ok", "type": "bool", "description": "Legacy pass flag — true only when result == 'pass'."},
        {"name": "result", "type": "str", "description": "Legacy validator result (pass/warn/info/fail/system-error/skip)."},
        {"name": "outcome", "type": "enum", "description": "Disambiguated outcome class — see ``outcomes`` below."},
        {"name": "counts", "type": "object", "description": "Finding counts: errors, warnings, infos."},
        {"name": "findings", "type": "list", "description": "Structured findings produced by the validator."},
        {"name": "findings_file", "type": "str|null", "description": "Path to persisted findings; null when omitted."},
        {"name": "issues", "type": "list", "description": "Issue summary list (legacy compatibility)."},
        {"name": "mode", "type": "str", "description": "Run mode (full / quick) — set by the validator."},
        {"name": "doc_exists", "type": "bool", "description": "Whether the target spec document is on disk."},
        {"name": "next_action", "type": "str", "description": "Human-readable next-step hint."},
        {"name": "next_action_command", "type": "str?", "description": "Concrete command when the doc is missing and a template is known."},
    ],
    "outcomes": [
        {
            "value": OUTCOME_PASS,
            "description": "Validator ran and the doc passed (no findings).",
        },
        {
            "value": OUTCOME_NOT_YET_AUTHORED,
            "description": (
                "Validator is registered for the doc kind but the file "
                "is missing on disk (or empty); the agent must write it "
                "from the template before retrying."
            ),
        },
        {
            "value": OUTCOME_LINT_FAILED,
            "description": "Doc exists but findings non-zero (errors or warnings).",
        },
        {
            "value": OUTCOME_VALIDATOR_NOT_REGISTERED,
            "description": (
                "No pre-launch validator is registered for the doc kind; "
                "template_resolve_commands is still emitted so the agent "
                "has the write-step command without running a checker."
            ),
        },
    ],
}


def _describe_envelope_payload() -> dict:
    """Return the structured self-description for the envelope."""
    return _ENVELOPE_DESCRIPTION


def _template_resolve_commands_for(ctx: PhaseContext, doc: str) -> dict[str, str]:
    """Emit ``template_resolve_commands`` keyed by target doc.

    pre-launch-check runs before the doc write, so the agent needs the
    exact ``util/resolve-template.py`` command up front. Reuses the
    shared builder in ``sdd_core.command_templates`` so this phase and
    ``--phase launch`` emit byte-identical strings.
    """
    if not doc:
        return {}
    return build_template_resolve_commands(
        doc, project_path=ctx.project_path, spec_name=ctx.target_name,
    )


def _findings_signature(findings: list) -> str:
    """Return a stable hash for a list of structured findings.

    Sorted by (rule_id, line, column) so cosmetic re-ordering does not
    look like a fresh signature. Used to detect when the agent is
    looping on the same set of findings without progress.
    """
    keys = []
    for finding in findings or []:
        if not isinstance(finding, dict):
            continue
        keys.append((
            finding.get("rule_id", ""),
            finding.get("line", 0),
            finding.get("column", 0),
            finding.get("match", ""),
        ))
    keys.sort()
    return hashlib.sha256(
        json.dumps(keys, separators=(",", ":")).encode("utf-8"),
    ).hexdigest()


def _repeat_history_path(findings_file: str | None) -> Path | None:
    """Return the side-car path that tracks repeat signatures.

    The plan file (``.pre-launch-findings.json``) is rewritten by
    ``lint-requirements.py`` on every run, so the rolling counter
    lives in a sibling ``.pre-launch-repeat.json`` instead.
    """
    if not findings_file:
        return None
    return Path(findings_file).with_suffix(".repeat.json")


def _read_history(history_path: Path) -> dict:
    try:
        with open(history_path, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _cleanup_repeat_history(findings_file: str | None) -> None:
    """Remove the repeat side-car file on a PASS run.

    Mirrors the ``.pre-launch-findings.json`` cleanup pattern already
    applied by ``lint-requirements.py::_persist_findings_file``.
    Validate-loop side-cars must disappear the first time findings
    clear — otherwise subsequent FAIL→PASS→FAIL sequences resurrect
    stale counter state.
    """
    history_path = _repeat_history_path(findings_file)
    if history_path is None:
        return
    try:
        history_path.unlink(missing_ok=True)
    except OSError:
        # Advisory cleanup — never fail the gate on filesystem errors.
        pass


def _detect_repeat(findings: list, findings_file: str | None) -> dict | None:
    """Return a ``repeat_detected`` envelope when the same findings recur.

    Stores the rolling ``repeat_signature`` / ``repeat_count`` pair in a
    side-car file so the validator's rewrite of the plan file does not
    clobber the counter. Any change to the findings signature resets
    the count. Empty ``findings`` (PASS) triggers the cleanup branch
    via :func:`_cleanup_repeat_history` — callers invoke it directly.
    """
    if not findings:
        return None
    history_path = _repeat_history_path(findings_file)
    if history_path is None:
        return None
    history = _read_history(history_path)
    signature = _findings_signature(findings)
    prior_signature = history.get("repeat_signature")
    prior_count = int(history.get("repeat_count") or 0)
    new_count = prior_count + 1 if prior_signature == signature else 1

    history["repeat_signature"] = signature
    history["repeat_count"] = new_count
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(history_path, "w", encoding="utf-8") as fh:
            json.dump(history, fh, indent=2)
            fh.write("\n")
    except OSError:
        pass

    if new_count < _REPEAT_LIMIT:
        return None
    return {
        "repeat_detected": True,
        "repeat_count": new_count,
        "repeat_limit": _REPEAT_LIMIT,
        "instruction": (
            "The same findings appeared on "
            f"{new_count} consecutive pre-launch-check runs. "
            "Stop iterating. Surface the findings to the user via "
            "AskQuestion and request explicit guidance instead of "
            "another fix attempt."
        ),
    }


def _doc_exists_on_disk(ctx: PhaseContext, doc: str) -> bool:
    """Return True when the target spec document is present on disk.

    Distinguishes "doc missing → write first" from "doc present → fix
    findings" so the envelope's ``next_action`` can name the correct
    recovery rather than always saying "fix findings".
    """
    if not doc or ctx.category != "spec" or not ctx.target_name:
        return False
    try:
        doc_path = _paths.spec_dir(Path(ctx.project_path), ctx.target_name) / doc
    except Exception:
        return False
    return doc_path.is_file()


def handle_pre_launch_check(args: argparse.Namespace) -> None:
    """Run the post-write validator without touching the gate session."""
    if getattr(args, "describe_envelope", False):
        output.success(
            _describe_envelope_payload(),
            "pre-launch-check envelope description",
        )
        return
    ctx = PhaseContext.from_args(args)
    doc = (getattr(args, "doc", "") or "").strip()
    template_resolve_commands = _template_resolve_commands_for(ctx, doc)
    authoring_guardrails = build_authoring_guardrails(doc)

    if ctx.category != "spec" or not should_run_precheck(doc, ctx.category):
        # No validator is registered for this doc kind. ``ok`` is ``None``
        # so downstream readers can distinguish "we deliberately did not
        # check" from "we checked and the doc passed".
        payload = {
            "ok": None,
            "skipped": True,
            "outcome": OUTCOME_VALIDATOR_NOT_REGISTERED,
            "reason": (
                "pre-launch-check validator not registered for this doc; "
                "template_resolve_commands is still emitted so the agent "
                "has the write-step command."
            ),
            "category": ctx.category,
            "doc": doc,
            "pre_launch_checklist_key": PRE_LAUNCH_CHECKLIST_KEY,
        }
        if template_resolve_commands:
            payload["template_resolve_commands"] = template_resolve_commands
        if authoring_guardrails:
            payload["authoring_guardrails"] = authoring_guardrails
        output.success(payload, "pre-launch-check skipped (validator not registered)")
        return

    result = run_precheck(
        doc, spec_name=ctx.target_name, project_path=ctx.project_path,
    )
    if not result.get("ran") or result.get("result") == "skip":
        # The validator IS registered, but it skipped — typical cause is
        # the doc not yet existing on disk. Surface ``not_yet_authored``
        # so the agent draws a different conclusion than from a "no
        # validator" skip: write the doc, then retry.
        payload = {
            "ok": None,
            "skipped": True,
            "outcome": OUTCOME_NOT_YET_AUTHORED,
            "reason": result.get("message") or "validator did not run",
            "doc": doc,
            "pre_launch_checklist_key": PRE_LAUNCH_CHECKLIST_KEY,
        }
        if template_resolve_commands:
            payload["template_resolve_commands"] = template_resolve_commands
            resolve_cmd = template_resolve_commands.get(doc)
            if resolve_cmd:
                payload["next_action_command"] = resolve_cmd
        if authoring_guardrails:
            payload["authoring_guardrails"] = authoring_guardrails
        output.success(payload, "pre-launch-check skipped (not yet authored)")
        return

    exit_code = result.get("exit_code")
    if exit_code not in (0, 1):
        retry_cmd = build_pre_launch_check_command(
            doc=doc,
            category=ctx.category,
            target_name=ctx.target_name,
            project_path=ctx.project_path or ".",
        )
        output.error(
            f"pre-launch-check system error (exit {exit_code}): "
            f"{result.get('message') or ''}",
            hint=(
                "Inspect lint-requirements.py output and retry "
                "--phase pre-launch-check."
            ),
            next_action_command=retry_cmd,
        )

    doc_exists = _doc_exists_on_disk(ctx, doc)
    resolve_cmd = template_resolve_commands.get(doc) if template_resolve_commands else None
    payload = build_pre_launch_payload(
        result, doc_exists=doc_exists, resolve_cmd=resolve_cmd, doc=doc,
    )
    if template_resolve_commands:
        payload["template_resolve_commands"] = template_resolve_commands
    if authoring_guardrails:
        payload["authoring_guardrails"] = authoring_guardrails
    payload["pre_launch_checklist_key"] = PRE_LAUNCH_CHECKLIST_KEY

    # PASS runs may leave ``findings_file`` unset (validator removes the
    # plan file on pass). Resolve the canonical path from the spec
    # coordinates so the repeat side-car can still be cleaned up.
    findings_file_for_cleanup = payload.get("findings_file") or (
        pre_launch_findings_path(
            ctx.category, ctx.target_name, ctx.project_path,
        ) if ctx.target_name else None
    )
    repeat = _detect_repeat(payload["findings"], findings_file_for_cleanup)
    if payload.get("ok"):
        # PASS — drop any stale repeat side-car so later cycles start
        # from a clean counter.
        _cleanup_repeat_history(findings_file_for_cleanup)
    if repeat is not None:
        payload.update(repeat)
        ask_payload = {
            "user_question_prompt": (
                "Pre-launch-check has surfaced the same findings on "
                f"{repeat['repeat_count']} consecutive runs. How would "
                "you like to proceed?"
            ),
            "questions": [
                {
                    "id": "pre-launch-repeat-escalation",
                    "prompt": (
                        "Same findings recurred — escalate to a human "
                        "decision instead of another auto-fix attempt."
                    ),
                    "options": [
                        {"id": "investigate", "label": "Pause and review the findings manually"},
                        {"id": "override", "label": "Acknowledge and continue (skip the guard)"},
                    ],
                }
            ],
        }
        payload["ask_question_payload"] = ask_payload

    counts = payload["counts"]
    outcome = payload["outcome"]
    builder = _OUTCOME_MESSAGE_BUILDERS.get(outcome, _format_lint_failed)
    output.success(payload, builder(counts, doc))


@dataclass
class PreLaunchCheckInput(PhaseInput):
    """Typed input for the ``pre-launch-check`` entry phase.

    Lifecycle fields live on the common parent parser; only
    phase-specific flags are declared here.
    """

    doc: str = field(
        default=None, metadata={
            "help": "Document filename (e.g. requirements.md)",
        },
    )
    describe_envelope: bool = field(
        default=False, metadata={
            "help": (
                "Print the JSON schema of the agent-facing response "
                "envelope and exit. Use this to read the outcome enum "
                "off the script instead of consulting prose docs."
            ),
        },
    )


@phase(
    name="pre-launch-check",
    emits=frozenset(),
    help="Run the post-write validator without touching the gate session",
    description=__doc__,
)
class PreLaunchCheckPhase(Phase):
    """Entry-style phase — runs the post-write validator without
    advancing gate state. Declared in
    :data:`review.transitions.ENTRY_PHASES` so the reachability
    property test treats it as standalone.
    """

    Input = PreLaunchCheckInput

    def handle(self, args: argparse.Namespace) -> None:
        handle_pre_launch_check(args)
