#!/usr/bin/env python3
"""Single entry point for skill pre-flight: init if needed, then health check.

Usage:
    .spec-workflow/sdd workspace/ensure-healthy.py [--workspace PATH] [--detect-only]

Behavior:
    1. If ``.spec-workflow/`` does not exist → run ``init.py``, then
       ``check-health.py`` to verify.
    2. If ``.spec-workflow/`` exists → run ``check-health.py`` (detect only).
    3. If issues found → run ``check-health.py --auto-fix`` (default).
    4. If ``--detect-only`` → report issues as structured JSON without repair.
    5. Healthy → ``output.success()``.
    6. Still failing after auto-fix → ``output.error()`` with per-failure hints.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
from pathlib import Path
from typing import Optional

from sdd_core import cli, handoffs, output, paths, session
from sdd_core import preflight_state as _preflight_state
from sdd_core.paths import WORKFLOW_DIR
from sdd_core.subprocess_dispatch import run_dispatched

# Workspace-only shim: no target / repo_id / phase consumed.
__sdd_context_needs__ = ("workspace",)

_INIT_SHIM = "init.py"
_HEALTH_SHIM = "check-health.py"
_UPDATE_QUALITY_SHIM = "review/update-quality.py"
_AUTO_FIX_FLAG = "--auto-fix"
_AUTO_REFRESH_STALE_FLAG = "--auto-refresh-stale"
_FORCE_TEMPLATE_REPAIR_FLAG = "--force-template-repair"
_WORKSPACE_FLAG = "--workspace"


def _extract_json(raw_output: str) -> dict | None:
    """Best-effort JSON extraction from potentially noisy subprocess output.

    1. Try parsing the entire string as JSON.
    2. Scan for the first ``{...}`` block (handles leading/trailing noise).
    3. Return None if nothing parseable is found.
    """
    try:
        return json.loads(raw_output)
    except (json.JSONDecodeError, ValueError):
        pass

    start = raw_output.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(raw_output[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw_output[start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break

    return None


def _names_resolved_in_current_session(workspace: str) -> set[str]:
    """Return advisory names already resolved by the active session.

    Reads the on-disk preflight rows and the current session token.
    A row counts only when it is both ``resolved=True`` and stamped
    with the active ``session_id``: a fresh process mints a new
    session, so previously-resolved rows from a dead session do not
    short-circuit re-detection.
    """
    if not workspace:
        return set()
    current_token = session.current_session_id(Path(workspace))
    if not current_token:
        return set()
    resolved: set[str] = set()
    for row in _preflight_state.load(workspace=workspace):
        if row.resolved and row.session_id == current_token:
            resolved.add(row.name)
    return resolved


def _success_with_advisories(
    data: dict,
    *,
    previous: list | None = None,
    ctx: object | None = None,
    workspace: str = "",
    refresh_actions: Optional[list[dict]] = None,
) -> None:
    """Emit ``output.success`` with a "Workspace is healthy" message.

    Suffixes the message with a comma-separated list of ``warn``-level
    advisories when any are present. Single source of truth so the
    pre-auto-fix and post-auto-fix success paths stay in lockstep.
    Attaches the agent-ergonomic shape: ``advisories`` list,
    concatenated ``banner`` string, and top-level
    ``next_action_command`` when any advisory is actionable.

    When ``previous`` is provided (post-auto-fix second pass),
    ``cleared``/``fix_error`` advisories are computed via
    :func:`sdd_core.advisories.diff_advisories` so the agent receives
    explicit closure signals instead of re-seeing the same banner.
    """
    from sdd_core.advisories import collect_warn, diff_advisories, make_banner

    current_checks = data.get("checks") or []
    if previous is not None:
        advisories = diff_advisories(previous, current_checks)
    else:
        advisories = collect_warn(current_checks)

    # Persist the unfiltered batch so the merge-aware writer carries
    # forward the row's prior `resolved`/`session_id`. Filtering the
    # agent-visible view happens after persist so a re-detected
    # advisory whose row is still session-resolved keeps both its
    # disk state AND its envelope-suppression on the next re-run.
    _preflight_state.persist(
        [a.to_payload() for a in advisories],
        workspace=workspace,
    )

    # Suppress advisories the active session has already resolved.
    # The disk row is preserved by the persist call above; only the
    # agent envelope hides the still-warning name.
    session_resolved = _names_resolved_in_current_session(workspace)
    if session_resolved:
        advisories = [a for a in advisories if a.name not in session_resolved]

    names = [a.name for a in advisories]
    suffix = f" — advisories: {', '.join(names)}" if names else ""

    if advisories:
        data["advisories"] = [a.to_payload() for a in advisories]
        data["banner"] = make_banner(advisories)
        actionable = [a for a in advisories if a.action_required]
        if actionable:
            data["action_required"] = True
            data["next_action_command"] = actionable[0].next_action_command

    if refresh_actions:
        data["refresh_actions"] = list(refresh_actions)

    resolved_from = dict(ctx.resolved_from) if ctx is not None else None
    output.success(
        data,
        f"Workspace is healthy{suffix}",
        ctx=ctx,
        resolved_from=resolved_from,
        handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
    )


def _has_actionable_warn(data: dict) -> bool:
    """Return True when the first-pass checks carry an action-required
    advisory. Used by ``main()`` to decide whether to force a second
    pass with ``--auto-fix`` even when ``healthy: True`` — otherwise
    ``warn``-level issues with a known fix (e.g. ``sdd_shim_present``
    outdated) would never get repaired automatically."""
    from sdd_core.advisories import collect_warn

    for a in collect_warn(data.get("checks") or []):
        if a.action_required:
            return True
    return False


def _refresh_stale_targets(data: dict, project_root: str) -> list[dict]:
    """Dispatch ``review/update-quality.py`` for each drifted target.

    Reads the ``review_quality_stale`` check's ``extra.targets`` list
    and runs the shim once per target. Returns the per-target
    invocation summaries so the success envelope can advertise the
    refresh action without re-emitting the underlying advisory.
    """
    refreshes: list[dict] = []
    for check in data.get("checks") or []:
        if check.get("name") != "review_quality_stale":
            continue
        if check.get("status") not in ("warn", "info"):
            continue
        extra = check.get("extra") or {}
        for target in extra.get("targets", []) or []:
            target_name = target.get("target_name") or ""
            category = target.get("category") or ""
            if not (target_name and category):
                continue
            proc = run_dispatched(
                _UPDATE_QUALITY_SHIM,
                "--type", category,
                "--target", target_name,
                project_path=project_root,
            )
            refreshes.append({
                "category": category,
                "target_name": target_name,
                "returncode": proc.returncode,
            })
    return refreshes


def _run_script(script_name: str, extra_args: Optional[list[str]] = None) -> dict:
    """Run a sibling workspace script and return parsed JSON from stdout."""
    proc = run_dispatched(
        f"workspace/{script_name}",
        *(extra_args or []),
    )

    stdout = proc.stdout.strip()
    if stdout:
        result = _extract_json(stdout)
        if result is not None:
            return result

    stderr = proc.stderr.strip()
    if stderr:
        result = _extract_json(stderr)
        if result is not None:
            return result

    return {"status": "error", "error": f"{script_name} exited {proc.returncode}", "stdout": stdout, "stderr": stderr}


def main() -> None:
    parser = cli.strict_parser("Ensure workspace is healthy (init + check)")
    parser.add_argument(_AUTO_FIX_FLAG, action="store_true", default=True,
                        help="Auto-repair detected issues (default: True)")
    parser.add_argument("--detect-only", action="store_true",
                        help="Detect and report only — skip repair")
    parser.add_argument(
        _FORCE_TEMPLATE_REPAIR_FLAG, action="store_true",
        help=(
            f"Pass {_FORCE_TEMPLATE_REPAIR_FLAG} through to {_HEALTH_SHIM} — "
            "permits overwrite of drifted templates with on-disk backup."
        ),
    )
    parser.add_argument(
        _AUTO_REFRESH_STALE_FLAG, action="store_true",
        help=(
            "When the review_quality_stale advisory fires, dispatch "
            "review/update-quality.py for each drifted target so the "
            "artifact converges in one pass."
        ),
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=("workspace",))

    if args.detect_only:
        args.auto_fix = False

    root = Path(paths.resolve_project_path(args)).resolve()
    workflow = root / WORKFLOW_DIR
    project_args = [_WORKSPACE_FLAG, str(root)]

    # Mint or reuse a session token up-front so resolved-in-session
    # bookkeeping has a stable id for the rest of this run.
    if workflow.is_dir():
        session.get_or_create_session_id(root)

    if not workflow.is_dir():
        init_result = _run_script(_INIT_SHIM, project_args)
        if init_result.get("status") == "error":
            output.preflight_required(
                {"phase": "init", "raw": init_result},
                f"Workspace initialization failed: {init_result.get('error', 'unknown')}",
                next_action_command=f"{_INIT_SHIM} {' '.join(project_args)}".strip(),
                hint=init_result.get("hint", "Check permissions and try again"),
            )

    check_result = _run_script(_HEALTH_SHIM, project_args)

    if check_result.get("status") == "error":
        output.preflight_required(
            {"phase": "check-health", "raw": check_result},
            f"Health check failed: {check_result.get('error', 'unknown')}",
            next_action_command=f"{_HEALTH_SHIM} {' '.join(project_args)}".strip(),
            hint=check_result.get("hint", ""),
        )

    data = check_result.get("data", check_result)
    first_pass_checks = list(data.get("checks") or [])

    # ``warn``-tier advisories with ``action_required: true`` have a
    # known repair path (e.g. stale ``sdd_shim_present``). Treat them
    # like unhealthy for the purpose of deciding whether to run auto-fix,
    # so the agent sees ``cleared: true`` instead of the same banner
    # twice. Still honour ``--detect-only`` — users asking for detection
    # never get an implicit repair.
    needs_autofix = (
        not data.get("healthy", False)
        or (args.auto_fix and _has_actionable_warn(data))
    )

    if not needs_autofix:
        refresh_actions = (
            _refresh_stale_targets(data, str(root))
            if getattr(args, "auto_refresh_stale", False) else None
        )
        _success_with_advisories(
            data, ctx=ctx, workspace=str(root),
            refresh_actions=refresh_actions,
        )
        return  # unreachable — output.success calls sys.exit

    issues = [c for c in data.get("checks", []) if c.get("status") not in ("pass", "warn")]

    if not args.auto_fix:
        from sdd_core.advisories import collect_warn
        warn_advisories = collect_warn(data.get("checks") or [])
        _preflight_state.persist(
            [a.to_payload() for a in warn_advisories],
            workspace=str(root),
        )
        # Suppress advisories the active session already resolved so
        # `--detect-only` does not re-surface a name that was just
        # cleared via resolve-advisory.py within this session.
        session_resolved = _names_resolved_in_current_session(str(root))
        if session_resolved:
            issues = [
                c for c in issues if c.get("name") not in session_resolved
            ]
        output.success(
            {
                "status": "issues_found",
                "healthy": False,
                "issues": issues,
                "checks": data.get("checks", []),
                "action_required": f"pass {_AUTO_FIX_FLAG} to repair, or address manually",
            },
            f"Workspace has {len(issues)} issue(s) — run with {_AUTO_FIX_FLAG} to repair",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
        )
        return  # unreachable

    autofix_args = [_AUTO_FIX_FLAG, *project_args]
    if getattr(args, "force_template_repair", False):
        autofix_args.append(_FORCE_TEMPLATE_REPAIR_FLAG)
    health_result = _run_script(_HEALTH_SHIM, autofix_args)

    if health_result.get("status") == "error":
        output.preflight_required(
            {"phase": "check-health-autofix", "raw": health_result},
            f"Health check failed: {health_result.get('error', 'unknown')}",
            next_action_command=f"{_HEALTH_SHIM} {' '.join(autofix_args)}".strip(),
            hint=health_result.get("hint", ""),
        )

    data = health_result.get("data", health_result)

    if data.get("healthy", False):
        refresh_actions = (
            _refresh_stale_targets(data, str(root))
            if getattr(args, "auto_refresh_stale", False) else None
        )
        _success_with_advisories(
            data, previous=first_pass_checks, ctx=ctx, workspace=str(root),
            refresh_actions=refresh_actions,
        )
        return  # unreachable

    still_failing = data.get("still_failing", [])
    failing_checks = [c for c in data.get("checks", []) if c.get("status") == "fail"]
    failures = still_failing or failing_checks

    hints = []
    for f in failures:
        name = f.get("name", "unknown")
        detail = f.get("detail", f.get("missing", ""))
        hints.append(f"{name}: {detail}")

    output.error(
        "Workspace still has issues after auto-fix",
        hint="; ".join(hints) if hints else "Run check-health.py for details",
    )


if __name__ == "__main__":
    cli.run_main(main)
