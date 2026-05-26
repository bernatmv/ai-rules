"""Pipeline pre-check helpers.

Shared helper functions for the launch phase of the review-approval
pipeline (``pre-approval-validation.md § Check 1c``). Keeps
``requirements.md`` antipattern invocation out of the phase-handler
proper so tests can exercise it directly.

Exits are structured via ``sdd_core.output`` — never via ``sys.exit``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict

from . import output
from . import paths as _paths
from .specs import is_bug_fix_spec
from .subprocess_dispatch import run_dispatched

__all__ = [
    "PreCheckResult",
    "RequirementsPreCheckResult",
    "TasksPreCheckResult",
    "should_run_requirements_check",
    "should_run_precheck",
    "run_requirements_precheck",
    "run_tasks_precheck",
    "run_design_precheck",
    "run_precheck",
    "build_launch_notes",
    "build_pre_launch_payload",
    "build_authoring_guardrails",
    "EMPTY_COUNTS",
    "full_counts",
    "OUTCOME_PASS",
    "OUTCOME_NOT_YET_AUTHORED",
    "OUTCOME_LINT_FAILED",
    "OUTCOME_VALIDATOR_NOT_REGISTERED",
]


# Disambiguated outcome classes for the pre-launch-check envelope.
# Adding a new branch is one constant + one row in
# ``_OUTCOME_PREDICATES`` below.
#
# ``validator_not_registered`` distinguishes "no validator exists for
# this doc kind" (skip, not authored vs. nothing to check) from
# ``not_yet_authored`` (validator exists, doc absent on disk) and from
# ``passed`` (validator ran and produced no findings). The three classes
# let agents route on outcome rather than parse the legacy ``ok`` /
# ``skipped`` flag pair, which collapsed two distinct states into one.
OUTCOME_PASS = "passed"
OUTCOME_NOT_YET_AUTHORED = "not_yet_authored"
OUTCOME_LINT_FAILED = "lint_failed"
OUTCOME_VALIDATOR_NOT_REGISTERED = "validator_not_registered"


EMPTY_COUNTS: dict[str, int] = {"errors": 0, "warnings": 0, "infos": 0}


def full_counts(counts: dict | None) -> dict[str, int]:
    """Return a dict guaranteed to carry ``errors``/``warnings``/``infos`` keys.

    The validator may return an empty dict when it failed before producing
    counts (e.g. "file not found"). Agents reading the envelope expect a
    stable shape, so we always surface the three keys.
    """
    base = dict(EMPTY_COUNTS)
    if isinstance(counts, dict):
        for key, value in counts.items():
            if key in base and isinstance(value, int):
                base[key] = value
    return base


_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
_VALIDATE_SCRIPT = _SCRIPTS_ROOT / "spec" / "lint-requirements.py"
_VALIDATE_TASKS_SCRIPT = _SCRIPTS_ROOT / "spec" / "lint-tasks.py"
_VALIDATE_DESIGN_SCRIPT = _SCRIPTS_ROOT / "spec" / "lint-design.py"
_VALIDATE_TRACEABILITY_SCRIPT = _SCRIPTS_ROOT / "spec" / "check-traceability.py"


def _script_name_for(target_script: Path) -> str:
    """Convert an absolute script path to a dispatcher-relative name.

    ``run_dispatched`` resolves names relative to ``SCRIPTS_ROOT`` so a
    caller passing a custom test fixture path can still ride the
    dispatcher contract. Falls back to the absolute path's filename
    when the script lives outside ``SCRIPTS_ROOT`` (defensive — only
    happens in tests overriding to a sibling directory).
    """
    target = Path(target_script).resolve()
    try:
        return str(target.relative_to(_SCRIPTS_ROOT.resolve()))
    except ValueError:
        return target.name


class PreCheckResult(TypedDict):
    """Structured result of a pre-check (requirements / tasks / etc.)."""

    ran: bool
    exit_code: int
    result: Literal["pass", "warn", "info", "fail", "system-error", "skip"]
    counts: dict[str, int]
    issues: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    findings_file: "str | None"
    mode: str
    message: str


# Aliases preserve the existing public names; both resolve to the
# unified :class:`PreCheckResult`.
RequirementsPreCheckResult = PreCheckResult
TasksPreCheckResult = PreCheckResult


def should_run_requirements_check(doc: str, category: str) -> bool:
    """Return True when the requirements precheck applies.

    Thin alias kept for backwards compatibility with existing callers.
    New code should use :func:`should_run_precheck` which dispatches
    on the per-doc runner table.
    """
    if category != "spec":
        return False
    return doc.strip().lower() == "requirements.md"


def should_run_precheck(doc: str, category: str) -> bool:
    """Return True when any per-doc precheck applies.

    Extension path: add a new entry to :data:`_DOC_PRECHECK_RUNNERS`
    and callers automatically route without editing this guard.
    """
    if category != "spec":
        return False
    return doc.strip().lower() in _DOC_PRECHECK_RUNNERS


def _resolve_requirements_path(
    project_path: str, spec_name: str, explicit_path: str | None = None,
) -> str:
    """Resolve the path to ``requirements.md`` for *spec_name*.

    Delegates to :func:`sdd_core.paths.spec_dir` so the
    ``.spec-workflow/specs/<name>/`` layout lives in exactly one place.
    """
    if explicit_path:
        return explicit_path
    return str(_paths.spec_dir(Path(project_path), spec_name) / "requirements.md")


def run_requirements_precheck(
    *,
    spec_name: str,
    project_path: str,
    requirements_path: str | None = None,
    mode: str | None = None,
    script_path: str | None = None,
) -> RequirementsPreCheckResult:
    """Invoke ``lint-requirements.py`` and classify the outcome.

    Returns a :class:`RequirementsPreCheckResult` the caller can translate
    into launch-payload fields (``pre_check_notes`` on pass/warn/info,
    ``output.error`` on fail).
    """
    target_script = Path(script_path) if script_path else _VALIDATE_SCRIPT
    req_path = _resolve_requirements_path(
        project_path, spec_name, explicit_path=requirements_path,
    )

    extra_args: list[str] = [req_path]
    if project_path:
        extra_args.extend(["--workspace", str(project_path)])
    effective_mode = mode
    if effective_mode is None and is_bug_fix_spec(spec_name):
        effective_mode = "bug-fix"
    if effective_mode:
        extra_args.extend(["--mode", effective_mode])

    proc = run_dispatched(_script_name_for(target_script), *extra_args)

    if proc.returncode == 0:
        envelope = _try_parse_json(proc.stdout)
        data = envelope.get("data") if envelope else {}
        result = (data or {}).get("result") or "pass"
        counts = (data or {}).get("counts") or dict(EMPTY_COUNTS)
        issues = (data or {}).get("issues") or []
        findings = (data or {}).get("findings") or []
        findings_file = (data or {}).get("findings_file")
        return RequirementsPreCheckResult(
            ran=True,
            exit_code=0,
            result=result,
            counts=counts,
            issues=issues,
            findings=findings,
            findings_file=findings_file,
            mode=(data or {}).get("mode") or effective_mode or "standard",
            message=envelope.get("message", "") if envelope else "",
        )

    if proc.returncode == 1:
        envelope = _try_parse_json(proc.stderr)
        issues, counts_from_ctx = _extract_issues_from_error(envelope)
        findings, findings_file = _extract_findings_from_error(envelope)
        return RequirementsPreCheckResult(
            ran=True,
            exit_code=1,
            result="fail",
            counts=counts_from_ctx,
            issues=issues,
            findings=findings,
            findings_file=findings_file,
            mode=effective_mode or "standard",
            message=(envelope.get("error") if envelope else proc.stderr).strip(),
        )

    # exit_code == 2 (system fault) or anything unexpected.
    return RequirementsPreCheckResult(
        ran=True,
        exit_code=proc.returncode,
        result="system-error",
        counts=dict(EMPTY_COUNTS),
        issues=[],
        findings=[],
        findings_file=None,
        mode=effective_mode or "standard",
        message=(proc.stderr or proc.stdout).strip(),
    )


def _resolve_tasks_path(
    project_path: str, spec_name: str, explicit_path: str | None = None,
) -> str:
    """Resolve the path to ``tasks.md`` for *spec_name*."""
    if explicit_path:
        return explicit_path
    return str(_paths.spec_dir(Path(project_path), spec_name) / "tasks.md")


def _tasks_skip_result(reason: str) -> "TasksPreCheckResult":
    return TasksPreCheckResult(
        ran=True,
        exit_code=0,
        result="skip",
        counts=dict(EMPTY_COUNTS),
        issues=[],
        findings=[],
        findings_file=None,
        mode="standard",
        message=reason,
    )


def _run_validator(
    script: "str | Path", *args: str,
) -> tuple[int, dict[str, Any] | None, dict[str, Any] | None]:
    """Invoke a validator subprocess and return (returncode, stdout, stderr).

    Envelopes decode to dicts when parseable, else ``None``.
    """
    if isinstance(script, Path):
        script_name = _script_name_for(script)
    else:
        script_name = script
    proc = run_dispatched(script_name, *args)
    return (
        proc.returncode,
        _try_parse_json(proc.stdout),
        _try_parse_json(proc.stderr),
    )


def run_tasks_precheck(
    *,
    spec_name: str,
    project_path: str,
    tasks_path: str | None = None,
    requirements_path: str | None = None,
    script_path: str | None = None,
    traceability_script_path: str | None = None,
) -> "TasksPreCheckResult":
    """Validate ``tasks.md`` structure and (when possible) traceability.

    Runs the Tier 1 scripts listed in
    ``review_quality.constants.TIER1_SCRIPT_SPECS`` for ``tasks_md``:

    * ``spec/lint-tasks.py`` (always, when ``tasks.md`` exists)
    * ``spec/check-traceability.py`` (when both ``requirements.md``
      and ``tasks.md`` exist)

    Returns a skip result when ``tasks.md`` does not exist yet — the
    pre-launch-check phase still emits its ``template_resolve_commands``
    so the agent can draft from the canonical template.
    """
    tasks_file = _resolve_tasks_path(
        project_path, spec_name, explicit_path=tasks_path,
    )
    if not Path(tasks_file).is_file():
        return _tasks_skip_result(
            "tasks.md not written yet — template_resolve_commands only"
        )

    target_tasks = Path(script_path) if script_path else _VALIDATE_TASKS_SCRIPT
    tasks_args: list[str] = [tasks_file]
    if project_path:
        tasks_args.extend(["--workspace", str(project_path)])

    rc_tasks, stdout_env, stderr_env = _run_validator(target_tasks, *tasks_args)

    issues: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    counts = dict(EMPTY_COUNTS)
    messages: list[str] = []
    tasks_outcome = "pass"

    if rc_tasks == 0:
        tasks_data = (stdout_env or {}).get("data") or {}
        passed = int(tasks_data.get("passed") or 0)
        failed = int(tasks_data.get("failed") or 0)
        if passed:
            messages.append(f"validate-tasks: {passed} passed")
        if failed:
            counts["errors"] += failed
            tasks_outcome = "fail"
    elif rc_tasks == 1:
        counts["errors"] += 1
        tasks_outcome = "fail"
        err_msg = (stderr_env or {}).get("error") if stderr_env else None
        messages.append(
            err_msg or "validate-tasks reported failures"
        )
        issues.append({
            "rule": "validate-tasks",
            "severity": "error",
            "message": err_msg or "validate-tasks reported failures",
        })
    else:
        return TasksPreCheckResult(
            ran=True,
            exit_code=rc_tasks,
            result="system-error",
            counts=dict(EMPTY_COUNTS),
            issues=[],
            findings=[],
            findings_file=None,
            mode="standard",
            message=((stderr_env or {}).get("error") if stderr_env else "") or "validate-tasks system error",
        )

    req_file = _resolve_requirements_path(
        project_path, spec_name, explicit_path=requirements_path,
    )
    if Path(req_file).is_file():
        target_trace = Path(traceability_script_path) if traceability_script_path else _VALIDATE_TRACEABILITY_SCRIPT
        trace_args: list[str] = ["--target", spec_name]
        if project_path:
            trace_args.extend(["--workspace", str(project_path)])
        rc_trace, trace_stdout, trace_stderr = _run_validator(
            target_trace, *trace_args,
        )
        if rc_trace == 0:
            trace_data = (trace_stdout or {}).get("data") or {}
            result_tag = trace_data.get("result")
            if result_tag == "not_applicable":
                messages.append("traceability: not applicable (bug-fix spec)")
            else:
                messages.append("traceability: full coverage")
        elif rc_trace == 1:
            counts["errors"] += 1
            tasks_outcome = "fail"
            err_msg = (trace_stderr or {}).get("error") if trace_stderr else None
            messages.append(err_msg or "traceability gaps found")
            issues.append({
                "rule": "validate-traceability",
                "severity": "error",
                "message": err_msg or "traceability gaps found",
            })

    return TasksPreCheckResult(
        ran=True,
        exit_code=0 if tasks_outcome == "pass" else 1,
        result=tasks_outcome,
        counts=counts,
        issues=issues,
        findings=findings,
        findings_file=None,
        mode="standard",
        message="; ".join(m for m in messages if m),
    )


def _resolve_design_path(
    project_path: str, spec_name: str, explicit_path: str | None = None,
) -> str:
    """Resolve the path to ``design.md`` for *spec_name*."""
    if explicit_path:
        return explicit_path
    return str(_paths.spec_dir(Path(project_path), spec_name) / "design.md")


def _design_skip_result(reason: str) -> "PreCheckResult":
    return PreCheckResult(
        ran=True,
        exit_code=0,
        result="skip",
        counts=dict(EMPTY_COUNTS),
        issues=[],
        findings=[],
        findings_file=None,
        mode="standard",
        message=reason,
    )


def run_design_precheck(
    *,
    spec_name: str,
    project_path: str,
    design_path: str | None = None,
    script_path: str | None = None,
) -> "PreCheckResult":
    """Validate ``design.md`` antipatterns via ``spec/lint-design.py``.

    Returns a skip result when ``design.md`` is not yet on disk so the
    pre-launch-check phase can still emit ``template_resolve_commands``
    for the agent to draft from the canonical template.
    """
    design_file = _resolve_design_path(
        project_path, spec_name, explicit_path=design_path,
    )
    if not Path(design_file).is_file():
        return _design_skip_result(
            "design.md not written yet — template_resolve_commands only"
        )

    target = Path(script_path) if script_path else _VALIDATE_DESIGN_SCRIPT
    extra_args: list[str] = [design_file]

    proc = run_dispatched(_script_name_for(target), *extra_args)

    if proc.returncode == 0:
        envelope = _try_parse_json(proc.stdout)
        data = (envelope or {}).get("data") or {}
        result_tag = data.get("result") or "pass"
        counts = data.get("counts") or dict(EMPTY_COUNTS)
        issues = data.get("issues") or []
        return PreCheckResult(
            ran=True,
            exit_code=0,
            result=result_tag,
            counts=counts,
            issues=issues,
            findings=[],
            findings_file=None,
            mode="standard",
            message=(envelope or {}).get("message", "") if envelope else "",
        )

    if proc.returncode == 1:
        envelope = _try_parse_json(proc.stderr)
        issues, counts_from_ctx = _extract_issues_from_error(envelope)
        return PreCheckResult(
            ran=True,
            exit_code=1,
            result="fail",
            counts=counts_from_ctx or dict(EMPTY_COUNTS),
            issues=issues,
            findings=[],
            findings_file=None,
            mode="standard",
            message=(
                ((envelope or {}).get("error") if envelope else proc.stderr)
                or ""
            ).strip(),
        )

    return PreCheckResult(
        ran=True,
        exit_code=proc.returncode,
        result="system-error",
        counts=dict(EMPTY_COUNTS),
        issues=[],
        findings=[],
        findings_file=None,
        mode="standard",
        message=(proc.stderr or proc.stdout).strip(),
    )


_DOC_PRECHECK_RUNNERS: dict[str, Callable[..., dict]] = {
    "requirements.md": run_requirements_precheck,
    "tasks.md": run_tasks_precheck,
    "design.md": run_design_precheck,
}


def run_precheck(doc: str, **kwargs) -> dict:
    """Dispatch to the per-doc precheck runner.

    Raises ``KeyError`` if *doc* is not registered — callers should
    gate on :func:`should_run_precheck` first.
    """
    return _DOC_PRECHECK_RUNNERS[doc.strip().lower()](**kwargs)


def build_launch_notes(result: "RequirementsPreCheckResult") -> dict | None:
    """Shape the warn/info portion of the launch payload.

    Returns ``None`` for a passing check so callers can use the result
    as a truthy flag for "anything to report". The error path is handled
    by the launch phase via ``output.error`` — this helper is solely the
    notes-bag formatter shared by the launch phase.
    """
    if not result.get("ran"):
        return None
    if result.get("result") == "pass":
        return None
    return {
        "check": "requirements-antipatterns",
        "result": result.get("result"),
        "mode": result.get("mode"),
        "counts": result.get("counts"),
        "issues": result.get("issues"),
        "validator_findings": result.get("findings") or [],
        "findings_file": result.get("findings_file"),
        "message": result.get("message"),
    }


def build_authoring_guardrails(doc: str) -> list[dict]:
    """Return the ``authoring_guardrails`` list for a pre-launch-check doc.

    Sourced from ``sdd_core.requirements_validation.iter_error_rules`` so
    YAML remains the single source of truth. Empty for any doc that does
    not carry a structured write-time ruleset (currently only
    ``requirements.md`` qualifies).
    """
    if doc.strip().lower() != "requirements.md":
        return []
    try:
        from sdd_core.requirements_validation import iter_error_rules
    except (ImportError, ModuleNotFoundError):
        return []
    return [dict(rule) for rule in iter_error_rules()]


def _is_pass(*, legacy_result: str | None, doc_exists: bool, counts: dict[str, int]) -> bool:
    # The legacy validator vocabulary uses "pass" (no -ed); the outcome
    # enum the agent reads is "passed". Treat both as the same state so
    # validator output stays untouched while the surface contract uses
    # the explicit verb.
    return legacy_result in {"pass", OUTCOME_PASS}


def _is_not_yet_authored(*, legacy_result: str | None, doc_exists: bool, counts: dict[str, int]) -> bool:
    return (
        not doc_exists
        and not counts.get("errors")
        and not counts.get("warnings")
    )


def _is_lint_failed(*, legacy_result: str | None, doc_exists: bool, counts: dict[str, int]) -> bool:
    return True


_OUTCOME_PREDICATES: tuple[tuple[Callable[..., bool], str], ...] = (
    (_is_pass, OUTCOME_PASS),
    (_is_not_yet_authored, OUTCOME_NOT_YET_AUTHORED),
    (_is_lint_failed, OUTCOME_LINT_FAILED),
)


def _classify_outcome(
    *, legacy_result: str | None, doc_exists: bool, counts: dict[str, int]
) -> str:
    """Return the disambiguated ``outcome`` value for a pre-launch-check run.

    Three branches collapse the legacy ``result="fail"`` into actionable
    classes so agents can route on outcome rather than parsing message
    strings.
    """
    for predicate, outcome in _OUTCOME_PREDICATES:
        if predicate(
            legacy_result=legacy_result, doc_exists=doc_exists, counts=counts,
        ):
            return outcome
    return OUTCOME_LINT_FAILED


def build_pre_launch_payload(
    result: "RequirementsPreCheckResult",
    *,
    doc_exists: bool,
    resolve_cmd: str | None = None,
    doc: str = "",
) -> dict:
    """Shape the success envelope for the pre-launch-check phase.

    The payload always carries the agent-stable keys (``ok``, ``result``,
    ``outcome``, ``counts``, ``findings``, ``findings_file``, ``issues``,
    ``mode``, ``doc_exists``, ``next_action``); ``next_action_command``
    is only set when the doc is missing and a template-resolve command
    is known.

    ``outcome`` disambiguates the legacy ``result="fail"`` value into
    ``not_yet_authored`` (doc missing) vs. ``lint_failed`` (doc present
    but findings non-zero). ``result``/``ok`` are kept byte-identical
    for legacy consumers.
    """
    legacy = result.get("result")
    counts = full_counts(result.get("counts"))
    findings = result.get("findings") or []
    findings_file = result.get("findings_file")
    ok = legacy in {"pass", OUTCOME_PASS}
    outcome = _classify_outcome(
        legacy_result=legacy, doc_exists=doc_exists, counts=counts,
    )

    next_action_command: str | None = None
    if ok:
        next_action = "proceed to --phase launch"
    elif outcome == OUTCOME_NOT_YET_AUTHORED and resolve_cmd:
        next_action = (
            f"resolve template, write {doc}, then retry --phase pre-launch-check"
            if doc else "resolve template, write doc, then retry --phase pre-launch-check"
        )
        next_action_command = resolve_cmd
    else:
        next_action = "fix findings, then retry --phase pre-launch-check"

    payload: dict = {
        "ok": ok,
        "result": legacy,
        "outcome": outcome,
        "counts": counts,
        "findings": findings,
        "findings_file": findings_file,
        "issues": result.get("issues") or [],
        "mode": result.get("mode"),
        "doc_exists": doc_exists,
        "next_action": next_action,
    }
    if next_action_command:
        payload["next_action_command"] = next_action_command
    return payload


def _try_parse_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _parse_error_context(
    envelope: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the parsed ``context`` dict from an error envelope or ``None``.

    The CLI wrapper emits ``context`` as a JSON string. This helper
    centralises the guard + decode + dict-check so
    :func:`_extract_issues_from_error` /
    :func:`_extract_findings_from_error` stay thin field pulls.
    """
    if not envelope:
        return None
    ctx = envelope.get("context") or ""
    if not isinstance(ctx, str) or not ctx:
        return None
    try:
        parsed = json.loads(ctx)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _extract_issues_from_error(
    envelope: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Parse ``context`` as JSON and return (issues, counts).

    The CLI wrapper emits ``context`` as a JSON string containing the
    structured findings and severity counts (see
    ``spec/lint-requirements.py``). Callers fall back to empty
    values when the envelope is missing, malformed, or non-JSON.
    """
    parsed = _parse_error_context(envelope)
    if parsed is None:
        return [], {}
    issues = parsed.get("issues") or []
    counts = parsed.get("counts") or {}
    if not isinstance(issues, list):
        issues = []
    if not isinstance(counts, dict):
        counts = {}
    return issues, counts


def _extract_findings_from_error(
    envelope: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Extract the structured findings + file path from an error envelope.

    Mirrors :func:`_extract_issues_from_error` but for the ``findings``
    and ``findings_file`` fields that ``lint-requirements.py`` began
    surfacing alongside ``issues``.
    """
    parsed = _parse_error_context(envelope)
    if parsed is None:
        return [], None
    findings = parsed.get("findings") or []
    if not isinstance(findings, list):
        findings = []
    findings_file = parsed.get("findings_file")
    if findings_file is not None and not isinstance(findings_file, str):
        findings_file = None
    return findings, findings_file
