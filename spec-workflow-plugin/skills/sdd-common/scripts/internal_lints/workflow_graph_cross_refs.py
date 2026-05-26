#!/usr/bin/env python3
"""Lint: cross-reference resolution for ``workflow-graph.json`` (Phase 0.5 V-0).

Every ``gate_prompt_id`` referenced from the workflow graph must exist
in ``prompt-registry.json``; every ``handoff_id`` must exist in
``handoff-registry.json``; every ``preconditions`` / ``validations``
identifier must resolve to a registered :class:`sdd_core.validators.Validator`.

The lint is data-driven: it reads the three registries (the graph and
the two foreign-key targets) and yields one finding per unresolved
reference. Structural errors detected by
:func:`sdd_core.workflow_graph.validate` (unknown transition phase ids,
duplicate phase ids, schema violations) surface as the same finding
shape so reviewers see one diff to ratchet.

Usage:
  workflow_graph_cross_refs.py            — scan and diff against baseline.
  workflow_graph_cross_refs.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
from pathlib import Path

from internal_lints import LintFinding
from internal_lints._dispatch import rule_id_for
from internal_lints.baseline import (
    diff_baseline,
    key_for,
    read_baseline,
    write_baseline,
)
from sdd_core import cli, output, paths, workflow_graph
from sdd_core.handoffs import HANDOFF_REGISTRY_FILENAME
from sdd_core.prompts import load_registry as _load_prompt_registry
from sdd_core.validators import registered_ids as _validator_ids

_RULE_ID = rule_id_for(__name__, __file__)


def _load_handoff_registry() -> dict:
    """Return the handoff registry as a plain dict (empty schema on miss)."""
    here = Path(__file__).resolve().parent  # internal_lints/
    scripts_root = here.parent  # scripts/
    target = scripts_root / HANDOFF_REGISTRY_FILENAME
    if not target.is_file():
        return {"schemaVersion": "1.0.0", "scripts": {}}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schemaVersion": "1.0.0", "scripts": {}}


def _graph_relpath() -> str:
    """Return the canonical repo-relative path to ``workflow-graph.json``."""
    return (
        ".cursor/skills/sdd-common/scripts/sdd_core/data/"
        + workflow_graph.WORKFLOW_GRAPH_FILENAME
    )


def analyze() -> list[LintFinding]:
    """Return one :class:`LintFinding` per unresolved cross-reference."""
    prompt_registry = _load_prompt_registry()
    handoff_registry = _load_handoff_registry()
    validator_set = set(_validator_ids())

    errors = workflow_graph.validate(
        prompt_registry=prompt_registry,
        handoff_registry=handoff_registry,
        validator_ids=validator_set,
    )
    file_rel = _graph_relpath()
    findings: list[LintFinding] = []
    for message in errors:
        findings.append(LintFinding(
            rule_id=_RULE_ID,
            severity="error",
            file=file_rel,
            line=0,
            message=message,
            extra={"reason": message},
        ))
    return findings


def _emit_envelope(findings: list[LintFinding], *, refresh: bool) -> None:
    observed = sorted({key_for(f) for f in findings})
    if refresh:
        write_baseline(_RULE_ID, observed)
        output.success(
            {"rule_id": _RULE_ID, "count": len(observed)},
            f"{_RULE_ID}: baseline refreshed",
        )
        return
    diff = diff_baseline(observed, rule_id=_RULE_ID)
    if diff["new"] or diff["stale"]:
        output.error(
            f"{_RULE_ID}: new={len(diff['new'])} stale={len(diff['stale'])}",
            hint="Fix the cross-reference errors or refresh the baseline.",
            next_action_command=(
                f".spec-workflow/sdd internal_lints/baseline-refresh.py "
                f"--rule {_RULE_ID}"
            ),
        )
    output.success({"known": diff["known"]}, f"{_RULE_ID}: clean")


def main() -> None:
    parser = cli.strict_parser(
        "Cross-reference lint for sdd_core/data/workflow-graph.json"
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    args = parser.parse_args()
    findings = analyze()
    _emit_envelope(findings, refresh=args.refresh)


if __name__ == "__main__":
    cli.run_main(main)
