#!/usr/bin/env python3
"""Pipeline orchestrator — ticks ``pipeline-tick.py`` until terminal.

The SKILL.md agent loop shrinks to a single invocation: this
orchestrator is the loop-as-a-script, not the loop-as-prose.

Behaviour:

* Each iteration shells ``pipeline-tick.py`` with the configured
  locator flags + any caller-supplied phase passthrough tail.
* The tick's envelope (a JSON object with ``status`` + ``data``) is
  emitted verbatim on stdout as a single NDJSON line.
* The orchestrator keeps ticking until one of:
    - the tick envelope's ``data.terminal`` is ``true`` (the single
      explicit stop signal), or
    - ``--max-ticks`` is reached (safety valve — defaults to 32), or
    - a tick exits non-zero (error propagates out as the orchestrator's
      own exit code).

The orchestrator never reshapes envelopes; it is a streaming forwarder
whose only job is the invariant-bound while-true loop. Any envelope
shape change is a phase / tick concern, not this script's.

Usage:
  pipeline-run.py --category <c> --target-name <n> [--workspace .]
                  [--max-ticks 32]
                  [-- <extra flags forwarded to the resolved phase>]
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import json
import os
import subprocess
import sys

from sdd_core import cli, output, paths

_HERE = os.path.dirname(os.path.abspath(__file__))
_PIPELINE_TICK = os.path.join(_HERE, "pipeline-tick.py")

# Default safety valve — review pipelines today finish in ≤ ~8 ticks
# (launch → post-review → {post-fix → check-revalidation}* → pre-approval
# → complete). 32 gives headroom for the deepest fix cycles plus
# ack-calls breaks, while still bounding a runaway loop.
_DEFAULT_MAX_TICKS = 32


def _split_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    """Split argv at the first bare ``--`` marker.

    Mirrors ``pipeline-tick.py`` — the tail is forwarded verbatim to
    every tick so e.g. ``--review-skill`` on the first launch tick
    reaches the phase dispatcher.
    """
    try:
        idx = argv.index("--")
    except ValueError:
        return argv, []
    return argv[:idx], argv[idx + 1:]


def build_parser() -> argparse.ArgumentParser:
    """Return the argparse parser.

    Exported so ``tests.test_next_action_command_parses`` can
    round-trip emitted invocations — keeps the agent-facing flag
    vocabulary a single-source-of-truth.
    """
    parser = cli.strict_parser(
        __doc__,
        epilog=(
            "Examples:\n"
            "  pipeline-run.py --category steering --target-name steering\n"
            "  pipeline-run.py --category spec --target-name my-feature -- "
            "--review-skill sdd-review-spec-docs --doc-list "
            "requirements.md --scope per-document\n"
        ),
    )
    parser.add_argument(
        "--category", default="spec",
        choices=("spec", "steering", "discovery"),
        help="Approval category",
    )
    parser.add_argument(
        "--target-name", "--spec-name", dest="target_name", default="",
        type=cli.name_type("target-name"),
        help="Spec name, steering name, or discovery project name",
    )
    parser.add_argument(
        "--max-ticks", type=int, default=_DEFAULT_MAX_TICKS,
        help=(
            f"Safety valve — stop after N ticks even if the envelope "
            f"does not signal terminal (default: {_DEFAULT_MAX_TICKS})."
        ),
    )
    return parser


def _is_terminal_envelope(envelope: dict) -> bool:
    """Return ``True`` when the envelope signals no further ticks.

    Single terminator: the orchestrator reads only
    ``data.terminal is True``. The terminal phase (``complete``) is
    responsible for setting this flag on its emitted envelope; no
    phase-name fallback.
    """
    data = envelope.get("data") or {}
    return data.get("terminal") is True


def _run_tick(args: argparse.Namespace, passthrough: list[str]) -> tuple[int, str, str]:
    """Shell ``pipeline-tick.py`` once and return ``(rc, stdout, stderr)``.

    Uses ``subprocess.run`` with captured stdio so the orchestrator
    can parse the envelope (terminality check) without losing the
    bytes it needs to forward downstream. stdout/stderr are mirrored
    to our own streams after capture so observers see the same
    content a direct tick invocation would have produced.
    """
    sub_argv: list[str] = [
        sys.executable, _PIPELINE_TICK,
        "--category", args.category,
        "--target-name", args.target_name,
        "--workspace", paths.resolve_project_path(args),
    ]
    if passthrough:
        sub_argv.append("--")
        sub_argv.extend(passthrough)
    result = subprocess.run(
        sub_argv, capture_output=True, text=True, check=False,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> None:
    argv_own, passthrough = _split_passthrough(sys.argv[1:])
    parser = build_parser()
    args = parser.parse_args(argv_own)

    if not args.target_name:
        output.error(
            "--target-name / --spec-name is required",
            hint=(
                "Provide the spec, steering, or discovery project name "
                "so the orchestrator can locate the gate session."
            ),
        )

    ticks = 0
    while ticks < args.max_ticks:
        ticks += 1
        rc, stdout_bytes, stderr_bytes = _run_tick(args, passthrough)
        if stderr_bytes:
            sys.stderr.write(stderr_bytes)
        if stdout_bytes:
            # NDJSON line per tick — pipe-friendly and replayable.
            sys.stdout.write(stdout_bytes)
            if not stdout_bytes.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()
        if rc != 0:
            sys.exit(rc)
        try:
            envelope = json.loads(stdout_bytes)
        except json.JSONDecodeError:
            # Non-JSON stdout is an anomaly — bail with a non-zero
            # exit so the caller surfaces the problem. Matches the
            # "solve, don't punt" principle — no silent continue.
            output.error(
                "pipeline-tick returned non-JSON output",
                hint=(
                    "Inspect stderr above; pipeline-tick always emits "
                    "envelope JSON on stdout."
                ),
            )
        if _is_terminal_envelope(envelope):
            return
    output.error(
        f"pipeline-run aborted after {args.max_ticks} ticks "
        "without hitting a terminal envelope",
        hint=(
            "Raise --max-ticks if the workflow legitimately needs more "
            "iterations, or inspect the gate session for a stuck phase."
        ),
    )


if __name__ == "__main__":
    cli.run_main(main)
