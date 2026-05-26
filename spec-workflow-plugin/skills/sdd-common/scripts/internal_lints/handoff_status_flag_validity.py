#!/usr/bin/env python3
"""Lint: every ``--status <X>`` literal in handoff-registry.json validates.

Every ``command`` in ``handoff-registry.json`` that targets
``update-tracker.py`` must carry only ``--status`` values that appear in
:data:`workspace_tracker_validation.VALID_STATUSES`. The lint reads
``VALID_STATUSES`` directly so a future status addition needs no edit
here.

Usage:
  .spec-workflow/sdd internal_lints/handoff_status_flag_validity.py
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re

from sdd_core import cli, handoffs, output
from sdd_core.workspace_tracker_validation import VALID_STATUSES

_TARGET_SCRIPT = "update-tracker.py"
_STATUS_FLAG_RE = re.compile(r"--status\s+([A-Za-z_][A-Za-z0-9_-]*)")


def _iter_status_values(command: str) -> list[str]:
    return _STATUS_FLAG_RE.findall(command)


def _audit() -> list[dict]:
    """Return one finding per invalid ``--status`` literal."""
    findings: list[dict] = []
    registry = handoffs.load_registry()
    scripts = registry.get("scripts") or {}
    for script_id, entry in scripts.items():
        for ho in entry.get("handoffs") or []:
            command = (ho.get("command") or "")
            if _TARGET_SCRIPT not in command:
                continue
            for value in _iter_status_values(command):
                if value not in VALID_STATUSES:
                    findings.append({
                        "script_id": script_id,
                        "handoff_id": ho.get("id"),
                        "invalid_status": value,
                        "command": command,
                    })
    return findings


def main() -> None:
    parser = cli.strict_parser(__doc__ or "")
    parser.parse_args()
    findings = _audit()
    if not findings:
        output.success(
            {"checked": _TARGET_SCRIPT, "valid_statuses": sorted(VALID_STATUSES)},
            "handoff-status-flag-validity: clean",
        )
    output.error(
        f"{len(findings)} invalid --status literal(s) in handoff-registry.json",
        hint=(
            "Either drop --status from the handoff command, or use a value "
            "in workspace_tracker_validation.VALID_STATUSES."
        ),
        context=str(findings),
    )


if __name__ == "__main__":
    cli.run_main(main)
