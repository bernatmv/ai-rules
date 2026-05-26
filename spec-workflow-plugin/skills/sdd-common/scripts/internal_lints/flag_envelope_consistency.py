#!/usr/bin/env python3
"""Lint: alias-grouping + sibling-flag-registry parity for ``_emit_unknown_flag_warn``.

Two assertions per ``.spec-workflow/sdd {group}/`` parser tree:

1. **Alias-group expansion** — ``_expand_alias_groups`` returns every
   alias on a matched action. We synthesise an alias group with two
   known opt-strings, run it through the helper, and assert both
   aliases land in the output.
2. **Sibling-flag registry coverage** — for every group with at least
   two scripts, ``sibling_flag_acceptance_dict`` yields a non-empty
   registry. An empty registry indicates the AST reflection silently
   dropped every script's parser.

Findings carry ``next_action_command`` pointing at the helper file
under ``sdd_core/`` so the fix is mechanical.

Usage:
  flag_envelope_consistency.py            — diff against baseline.
  flag_envelope_consistency.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path
from typing import Final

from internal_lints import LintFinding
from internal_lints._dispatch import rule_id_for
from internal_lints.base import LintSpec, _emit_envelope, _resolve_repo
from sdd_core import cli

_RULE_ID = rule_id_for(__name__, __file__)

_SCRIPTS_ROOT_GLOB = ".spec-workflow/sdd"

_TEST_GROUPS: Final[tuple[str, ...]] = (
    "approval", "review", "spec", "util", "workspace", "internal_lints",
)

# Synthetic alias-group fixture used by ``_check_alias_expansion``.
# Names a primary flag plus the aliases ``_expand_alias_groups`` must
# surface when the primary lands in the typed-flag set.
_SYNTHETIC_PRIMARY: Final[str] = "--target"
_SYNTHETIC_ALIAS_GROUP: Final[tuple[str, ...]] = (
    "--target", "--spec-name", "--target-name",
)
_EXPECTED_EXPANSIONS: Final[tuple[str, ...]] = (
    "--spec-name", "--target-name",
)


def _check_alias_expansion() -> list[LintFinding]:
    """Round-trip ``_expand_alias_groups`` against a synthetic group."""
    findings: list[LintFinding] = []
    helper = getattr(cli, "_expand_alias_groups", None)
    if helper is None:
        findings.append(LintFinding(
            rule_id=_RULE_ID,
            severity="error",
            file=str(Path(cli.__file__)),
            line=0,
            message=(
                "sdd_core.cli._expand_alias_groups is missing — alias "
                "grouping for did_you_mean has regressed."
            ),
        ))
        return findings
    out = helper([_SYNTHETIC_PRIMARY], [_SYNTHETIC_ALIAS_GROUP])
    missing = [a for a in _EXPECTED_EXPANSIONS if a not in out]
    if missing:
        findings.append(LintFinding(
            rule_id=_RULE_ID,
            severity="error",
            file=str(Path(cli.__file__)),
            line=0,
            message=(
                "_expand_alias_groups dropped an alias on a matched group; "
                f"saw {out!r}, expected {list(_EXPECTED_EXPANSIONS)}."
            ),
        ))
    return findings


def _check_sibling_registry() -> list[LintFinding]:
    """Every multi-script group must yield a populated registry."""
    findings: list[LintFinding] = []
    try:
        from sdd_core.flag_context import (
            scripts_root, sibling_flag_acceptance_dict,
        )
    except ImportError as exc:
        findings.append(LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=_SCRIPTS_ROOT_GLOB, line=0,
            message=f"sdd_core.flag_context import failed: {exc}",
        ))
        return findings

    root = scripts_root()
    if root is None:
        return findings

    for group in _TEST_GROUPS:
        group_dir = root / group
        if not group_dir.is_dir():
            continue
        scripts = sorted(
            p.name for p in group_dir.glob("*.py")
            if not p.name.startswith("_")
        )
        if len(scripts) < 2:
            continue
        try:
            registry = sibling_flag_acceptance_dict(group)
        except Exception as exc:
            findings.append(LintFinding(
                rule_id=_RULE_ID, severity="error",
                file=str(group_dir), line=0,
                message=(
                    f"sibling_flag_acceptance_dict({group!r}) raised "
                    f"{type(exc).__name__}: {exc}"
                ),
            ))
            continue
        if not registry:
            findings.append(LintFinding(
                rule_id=_RULE_ID, severity="error",
                file=str(group_dir), line=0,
                message=(
                    f"sibling_flag_acceptance_dict({group!r}) is empty — "
                    "AST reflection dropped every script's parser. Check "
                    "that scripts declare flags via top-level "
                    "parser.add_argument calls."
                ),
            ))
    return findings


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills/sdd-common/scripts/sdd_core",),
)


def main() -> None:
    parser = cli.strict_parser(__doc__ or "")
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    args = parser.parse_args()
    _ = _resolve_repo()
    findings: list[LintFinding] = []
    findings.extend(_check_alias_expansion())
    findings.extend(_check_sibling_registry())
    _emit_envelope(SPEC, findings, refresh=args.refresh)


if __name__ == "__main__":
    cli.run_main(main)
