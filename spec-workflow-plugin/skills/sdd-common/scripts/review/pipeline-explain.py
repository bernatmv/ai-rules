#!/usr/bin/env python3
"""Pipeline introspection — human-readable explainer for gate state.

Ships the debug surface that lives next to ``pipeline/tick``:

* Resolves a gate session (category + target-name) and prints a
  human-readable description of:
    - current ``required_next_phase`` and the set of phases that
      :func:`review.transitions.allowed_previous` allows as callers,
    - reachable forward phases from the current state,
    - the transition graph as a Mermaid-style adjacency list (so the
      reference doc's diagram can be regenerated from this source).
* Optionally dumps the raw transition graph (``--graph``) so CI and
  gendoc tooling can consume the authoritative shape.

Design constraints:

* **No shell-state mutation.** Read-only; the script never writes
  the gate session.
* **Shares the transitions authority.** All phase-name strings come
  from :data:`review.transitions.TRANSITIONS`; nothing is hardcoded.
  When the graph changes, so does the explainer — no second place
  to sync.
* **Debuggability without rendering drift.** The command-string view
  of a pending tool call, when present, is pulled verbatim from the
  gate's persisted ``pending_tool_calls[]`` entries. We don't
  re-render; the live envelope is the source.

Usage:
  pipeline-explain.py --category spec --target-name my-feature
  pipeline-explain.py --graph
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import json
import os
import sys

from sdd_core import cli, output, paths
from review_quality.gate_session import read_session

from review.transitions import (
    ACK_PHASES,
    ENTRY_PHASES,
    TRANSITIONS,
    TERMINAL_PHASES,
    all_phases,
    allowed_previous,
    reachable_from,
)
from review.phase_kit import registered_phases
# Import side-effects — importing the package triggers every
# ``@phase`` decorator so ``registered_phases()`` sees the full set.
import review.pipeline_phases  # noqa: F401


def _build_parser() -> argparse.ArgumentParser:
    parser = cli.strict_parser(
        __doc__,
        epilog=(
            "Examples:\n"
            "  pipeline-explain.py --category spec --target-name my-feature\n"
            "  pipeline-explain.py --graph\n"
            "  pipeline-explain.py --graph --format json\n"
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
        "--graph", action="store_true",
        help=(
            "Dump the declarative transition graph and exit. Session "
            "lookup is skipped in this mode."
        ),
    )
    parser.add_argument(
        "--format", default="text", choices=("text", "json"),
        help="Output format (default: text).",
    )
    return parser


def _build_graph_view() -> dict:
    """Return a JSON-serialisable dump of the authoritative graph.

    Single helper consumed by ``--graph`` callers so a diagram edit is
    a single patch to the data shape.
    """
    transitions_dump = {
        name: sorted(nexts) for name, nexts in TRANSITIONS.items()
    }
    registry_dump = {
        name: {
            "emits": sorted(spec.emits),
            "help": spec.help,
            "class": f"{spec.cls.__module__}.{spec.cls.__qualname__}",
        }
        for name, spec in sorted(registered_phases().items())
    }
    return {
        "transitions": transitions_dump,
        "ack_phases": sorted(ACK_PHASES),
        "entry_phases": sorted(ENTRY_PHASES),
        "terminal_phases": sorted(TERMINAL_PHASES),
        "all_phases": sorted(all_phases()),
        "registered_phases": registry_dump,
    }


def _format_graph_text(graph: dict) -> str:
    """Return a human-readable adjacency listing of the graph."""
    lines = ["Pipeline transition graph:"]
    for phase in sorted(graph["transitions"]):
        nexts = graph["transitions"][phase]
        arrow = " → " + ", ".join(nexts) if nexts else "  (terminal)"
        lines.append(f"  {phase}{arrow}")
    lines.append("")
    lines.append(f"Ack phases (injected): {', '.join(graph['ack_phases'])}")
    lines.append(f"Entry phases (direct):  {', '.join(graph['entry_phases'])}")
    lines.append(f"Terminal phases:        {', '.join(graph['terminal_phases'])}")
    lines.append("")
    if graph["registered_phases"]:
        lines.append("@phase-decorated phases:")
        for name, info in sorted(graph["registered_phases"].items()):
            emits = ", ".join(info["emits"]) or "(terminal)"
            lines.append(f"  {name}: emits {emits} — {info['class']}")
    else:
        lines.append("No phases have migrated to @phase decorator yet.")
    return "\n".join(lines)


def _explain_session(
    category: str, target_name: str, project_path: str,
) -> dict:
    """Return a JSON-serialisable summary of the live gate state."""
    session = read_session(category, target_name, project_path)
    gate = session.get("review_gate") or {}
    expected = gate.get("required_next_phase") or "launch"
    pending = gate.get("pending_tool_calls") or []
    forward = sorted(reachable_from(expected))
    allowed_now = sorted(allowed_previous(expected))
    return {
        "category": category,
        "target_name": target_name,
        "gate_id": gate.get("gate_id"),
        "gate_uuid": gate.get("gate_uuid"),
        "required_next_phase": expected,
        "allowed_callers": allowed_now,
        "forward_reachable": forward,
        "pending_tool_calls": pending,
        "fix_cycle": gate.get("fix_cycle"),
        "max_cycles": gate.get("max_cycles"),
        "review_scope": gate.get("review_scope"),
    }


def _format_session_text(summary: dict) -> str:
    lines = [
        f"Gate for {summary['category']}/{summary['target_name']}:",
        f"  gate_id         : {summary.get('gate_id') or '(none)'}",
        f"  gate_uuid       : {summary.get('gate_uuid') or '(none)'}",
        f"  next phase      : {summary['required_next_phase']}",
        f"  allowed callers : {', '.join(summary['allowed_callers'])}",
        f"  forward reach   : {', '.join(summary['forward_reachable'])}",
        f"  fix_cycle       : {summary.get('fix_cycle')}",
        f"  max_cycles      : {summary.get('max_cycles')}",
        f"  review_scope    : {summary.get('review_scope')}",
    ]
    pending = summary.get("pending_tool_calls") or []
    if pending:
        lines.append(f"  pending calls   : {len(pending)}")
        for i, call in enumerate(pending, 1):
            kind = call.get("kind") or call.get("tool") or "(unknown)"
            reason = call.get("reason") or ""
            lines.append(f"    [{i}] {kind}  {reason}".rstrip())
    else:
        lines.append("  pending calls   : none")
    return "\n".join(lines)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.graph:
        graph = _build_graph_view()
        if args.format == "json":
            sys.stdout.write(json.dumps(graph, indent=2, sort_keys=True))
            sys.stdout.write("\n")
        else:
            sys.stdout.write(_format_graph_text(graph))
            sys.stdout.write("\n")
        return

    if not args.target_name:
        output.error(
            "--target-name / --spec-name is required (or pass --graph)",
            hint=(
                "Provide the spec / steering / discovery name so the "
                "explainer can locate the gate session."
            ),
        )

    project_path = paths.resolve_project_path(args)
    summary = _explain_session(args.category, args.target_name, project_path)

    if args.format == "json":
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_format_session_text(summary))
        sys.stdout.write("\n")


if __name__ == "__main__":
    cli.run_main(main)
