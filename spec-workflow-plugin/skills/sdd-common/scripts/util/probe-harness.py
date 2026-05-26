#!/usr/bin/env python3
"""Detect the active agent harness and persist the capability snapshot.

Writes ``<project>/.spec-workflow/.sdd-state/harness.json`` containing
the detected harness identifier plus a capability map the rest of the
pipeline consumes via :mod:`sdd_core.harness.loader`.

Resolution is delegated to :func:`sdd_core.harness.detectors.resolve_detection`
so the probe and the loader share one detector registry. The ``--variant``
flag is re-expressed as an env-var injection before resolution.

Usage:
  util/probe-harness.py                    # detect + persist
  util/probe-harness.py --workspace .   # detect + persist for a project
  util/probe-harness.py --dry-run          # detect + print, don't persist
  util/probe-harness.py --reset            # remove any stored harness.json
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
import os

from sdd_core import cli, output
from sdd_core.harness import (
    available_adapter_names,
    get_adapter,
)
from sdd_core.harness.adapter import HarnessAdapter, SelfcheckResult
from sdd_core.harness.detectors import (
    DetectionContext,
    HarnessContradictionError,
    resolve_detection,
)
from sdd_core.harness.loader import harness_state_path
from sdd_core.harness.state import build_state, write_state


class ProbeOutcome:
    """Library-level return type for :func:`probe_and_persist`."""

    def __init__(
        self,
        *,
        ok: bool,
        name: str = "",
        probe_method: str = "",
        state: "dict | None" = None,
        path: str = "",
        error_message: str = "",
        error_hint: str = "",
    ) -> None:
        self.ok = ok
        self.name = name
        self.probe_method = probe_method
        self.state = state or {}
        self.path = path
        self.error_message = error_message
        self.error_hint = error_hint


__sdd_manifest__ = {
    "summary": "Detect the active agent harness and persist capabilities",
    "verbs": [
        "(no flags) — detect + persist",
        "--dry-run — detect + print",
        "--reset — remove harness.json",
        "--variant {auto|standard|task} — Claude Code sub-variant",
    ],
    "flags": [
        "--workspace", "--variant", "--dry-run", "--reset", "--strict",
    ],
}


def _run_selfcheck(adapter: HarnessAdapter) -> list[SelfcheckResult]:
    try:
        return list(adapter.selfcheck())
    except Exception as exc:  # pragma: no cover — defensive
        return [SelfcheckResult("selfcheck.dispatch", False, str(exc))]


def probe_and_persist(
    project_path: str,
    *,
    variant: str = "auto",
    dry_run: bool = False,
    strict: bool = False,
) -> ProbeOutcome:
    """Detect + selfcheck + persist via the shared detector registry.

    ``variant="task"`` injects ``CLAUDE_CODE_TASK_VARIANT=1`` so users
    on Claude Code can pin the Task-variant adapter even when the marker
    is not naturally set. ``strict=True`` surfaces a safe-default
    resolution as an ``unknown_harness`` error.
    """
    env = dict(os.environ)
    if variant == "task":
        env.setdefault("CLAUDE_CODE_TASK_VARIANT", "1")

    ctx = DetectionContext(
        project_path=project_path,
        env=env,
        state_path=harness_state_path(project_path),
    )
    try:
        outcome = resolve_detection(ctx)
    except HarnessContradictionError as exc:
        return ProbeOutcome(
            ok=False,
            error_message=exc.message,
            error_hint=exc.hint,
        )

    if strict and outcome.source == "safe_default":
        return ProbeOutcome(
            ok=False,
            error_message="unknown_harness",
            error_hint=(
                "No strong signal. Set SDD_HARNESS_OVERRIDE to one "
                f"of: {', '.join(available_adapter_names())}"
            ),
        )

    name = outcome.adapter_name
    adapter = get_adapter(name)
    selfcheck = _run_selfcheck(adapter)
    failed = [r for r in selfcheck if not r.passed]
    if failed:
        return ProbeOutcome(
            ok=False,
            name=name,
            probe_method=outcome.source,
            error_message=f"selfcheck_failed for adapter {name!r}",
            error_hint="; ".join(
                f"{r.capability}: {r.detail}" for r in failed
            ),
        )

    state = build_state(
        name, probe_method=outcome.source, include_capabilities=True,
    )
    path = harness_state_path(project_path)
    if not dry_run:
        write_state(state, project_path)
    return ProbeOutcome(
        ok=True, name=name, probe_method=outcome.source,
        state=state, path=path,
    )


def _maybe_reset(project_path: str) -> None:
    path = harness_state_path(project_path)
    if not os.path.isfile(path):
        output.success(
            {"path": path, "removed": False},
            "No harness.json to remove",
        )
        return
    try:
        os.unlink(path)
    except OSError as exc:
        output.error(f"Failed to delete {path}: {exc}")
    output.warn(f"Removed harness.json at {path}")
    output.success({"path": path, "removed": True}, "harness.json cleared")


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "--variant", default="auto", choices=("auto", "standard", "task"),
        help=(
            "Claude Code sub-variant hint. 'auto' picks the standard "
            "variant when the Task-variant marker is absent."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Detect the harness and print the envelope without persisting.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete any existing harness.json under the project.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help=(
            "Exit with a structured error when detection falls through "
            "to the safe-default detector."
        ),
    )
    args = parser.parse_args()

    project_path = os.path.abspath(args.project_path or ".")

    if args.reset:
        _maybe_reset(project_path)
        return

    outcome = probe_and_persist(
        project_path,
        variant=args.variant,
        dry_run=args.dry_run,
        strict=args.strict,
    )
    if not outcome.ok:
        output.error(outcome.error_message, hint=outcome.error_hint)

    if args.dry_run:
        print(json.dumps(
            {"state": outcome.state, "path": outcome.path}, indent=2,
        ))
        return

    output.success(
        {"path": outcome.path, "state": outcome.state},
        f"Detected harness: {outcome.name}",
    )


if __name__ == "__main__":
    cli.run_main(main)
