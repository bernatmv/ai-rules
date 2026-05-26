#!/usr/bin/env python3
"""Regenerate / prune internal-lint baselines.

Refreshes one rule (``--rule <id>``) or every rule (``--all``) inside
the consolidated ``baselines.json`` manifest.

Usage:
  baseline-refresh.py --rule <id>           # dry-run diff for one rule
  baseline-refresh.py --rule <id> --prune   # rewrite that rule's entries
  baseline-refresh.py --all --prune         # rewrite every rule

Exit codes: 0 on success, 1 on drift.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import importlib
import json

from sdd_core import cli, output
from sdd_core.command_templates import build_baseline_refresh_command

from internal_lints._dispatch import DISPATCH
from internal_lints.baseline import MANIFEST_PATH, _load_manifest


def _rule_modules() -> tuple[tuple[str, str], ...]:
    """Derive ``(rule_label, module_path)`` from the single dispatch registry.

    Adding a row to ``internal_lints/_dispatch.DISPATCH`` automatically
    pulls the rule into ``--all`` — no second registry to keep in
    lockstep.
    """
    return tuple((row.rule_label, row.module_path) for row in DISPATCH)


def _refresh_one(rule_id: str, *, prune: bool) -> dict:
    mod_name = next(
        (m for r, m in _rule_modules() if r == rule_id), None,
    )
    if not mod_name:
        return {"rule_id": rule_id, "status": "unknown"}
    mod = importlib.import_module(mod_name)
    if not (hasattr(mod, "analyze") and hasattr(mod, "compare_baseline")):
        # Rules emitted via the SKILL.md content-lint plumbing do not
        # ride the analyze/compare_baseline contract. Skip without
        # raising — surfaced as a structured status so the caller's
        # ``drift`` aggregation stays clean.
        return {"rule_id": rule_id, "status": "skipped:no-analyze-contract"}
    findings = mod.analyze()
    diff = mod.compare_baseline(findings)
    summary = {
        "rule_id": rule_id,
        "new": diff["new"],
        "stale": diff["stale"],
        "known": diff["known"],
    }
    if prune:
        from internal_lints.baseline import write_baseline
        # ``diff["known"] + diff["new"]`` is exactly the set the rule's
        # ``compare_baseline`` deemed eligible — already filtered for
        # rules whose findings are heterogeneous (e.g. ``error_envelopes``
        # only baselines exempt findings, not error/hint-only ones).
        observed = sorted(set(diff["known"]) | set(diff["new"]))
        write_baseline(rule_id, observed)
        summary["pruned"] = True
    return summary


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("--rule", default=None, help="Rule id to refresh")
    parser.add_argument(
        "--all", action="store_true",
        help="Iterate every rule in the manifest",
    )
    parser.add_argument(
        "--prune", action="store_true",
        help="Rewrite baseline entries to the observed set",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report drift without rewriting (default)",
    )
    args = parser.parse_args()

    targets: list[str]
    if args.all:
        targets = [r for r, _m in _rule_modules()]
    elif args.rule:
        targets = [args.rule]
    else:
        targets = ["error-envelopes"]

    summaries = [_refresh_one(t, prune=args.prune) for t in targets]
    drift = [s for s in summaries if s.get("new") or s.get("stale")]

    payload = {
        "manifest_path": str(MANIFEST_PATH),
        "summaries": summaries,
    }
    message = (
        f"baselines: {len(summaries)} rule(s), "
        f"{len(drift)} with drift"
    )
    if drift and not args.prune:
        output.error(
            message,
            hint="Pass --prune to rewrite, or fix the call sites",
            context=json.dumps({"drift": drift}),
            next_action_command=build_baseline_refresh_command(
                args.rule or "error-envelopes", prune=True,
            ),
        )
    output.success(payload, message)


if __name__ == "__main__":
    cli.run_main(main)


# Re-export for tests that introspect the manifest loader directly.
__all__ = ["MANIFEST_PATH", "_load_manifest"]
