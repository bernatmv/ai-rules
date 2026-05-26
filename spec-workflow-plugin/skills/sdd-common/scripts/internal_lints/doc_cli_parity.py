#!/usr/bin/env python3
"""Lint doc/CLI flag drift declared in ``data/doc_cli_flag_parity.yaml``.

Every entry binds a reference doc to a script; required flags must
exist on the script's argparse, forbidden flags must not appear in
the doc body when the bound script is the invocation context.

Usage:
  internal_lints/doc_cli_parity.py
  internal_lints/doc_cli_parity.py --baseline-write
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, doc_cli_parity, output

__sdd_manifest__ = {
    "summary": "Doc-cited flags must resolve to the bound script's argparse",
    "verbs": ["(no args)", "--baseline-write"],
    "flags": ["--baseline-write"],
}


def _recovery_for_finding(finding: doc_cli_parity.Finding) -> str:
    """Return a literal $EDITOR recovery for a parity finding.

    Drops the prior ``--baseline`` punt: forbidden flags are removed
    from the doc rather than baselined; missing required flags are
    surfaced as edit instructions naming the canonical surface.
    """
    if finding.kind == doc_cli_parity.FINDING_KIND_FORBIDDEN_FLAG_IN_DOC:
        return (
            f"$EDITOR .cursor/skills/sdd-common/{finding.rule.reference}  "
            f"# remove obsolete {finding.flag} (no longer accepted by "
            f"{finding.rule.script})"
        )
    return (
        f"$EDITOR .cursor/skills/sdd-common/scripts/{finding.rule.script}  "
        f"# expose {finding.flag} on argparse, then re-run the lint"
    )


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "--baseline-write",
        action="store_true",
        help="Emit findings to stdout for explicit baseline mutation tooling",
    )
    args = parser.parse_args()

    findings = doc_cli_parity.run_all()

    if args.baseline_write:
        output.success(
            {
                "findings": [
                    {
                        "kind": f.kind,
                        "flag": f.flag,
                        "reference": f.rule.reference,
                        "script": f.rule.script,
                        "detail": f.detail,
                    }
                    for f in findings
                ],
                "count": len(findings),
            },
            f"{len(findings)} doc/CLI parity violation(s)",
        )
        return

    if findings:
        recovery_lines = [
            f"{f.detail}\nRecovery: {_recovery_for_finding(f)}"
            for f in findings
        ]
        output.error(
            f"{len(findings)} doc/CLI flag-parity violation(s)",
            hint="\n\n".join(recovery_lines),
            next_action_command=_recovery_for_finding(findings[0]),
        )
        return
    output.success(
        {"checked": len(doc_cli_parity.load_rules())},
        "All doc-cited flags resolve to their bound scripts",
    )


if __name__ == "__main__":
    cli.run_main(main)
