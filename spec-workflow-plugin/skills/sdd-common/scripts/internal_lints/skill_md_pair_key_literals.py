#!/usr/bin/env python3
"""Lint reference docs for legacy ``__``-joined cross-validation pair keys.

Canonical pair keys use the ``_x_`` separator between two full
``doc_key``s (e.g. ``product_md_x_tech_md``). Reference docs that
carry the legacy ``<a_md>__<b_md>`` shape drift from the single
source of truth (``review_quality/canonical_cross_validation_keys``)
and teach sub-agents the wrong shape.

Enforced primarily against ``**/references/artifact-assessment-format.md``
— the two files where the drift was observed — but extends to every
reference / SKILL.md body so future copies can't quietly reintroduce
the stale shape.

Usage:
  internal_lints/skill_md_pair_key_literals.py --path <file.md>
  internal_lints/skill_md_pair_key_literals.py --all
  internal_lints/skill_md_pair_key_literals.py --baseline
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re

from sdd_core import cli
from internal_lints._skill_md_lint_cli import make_literal_lint, run_skill_md_lint

__sdd_manifest__ = {
    "summary": "Lint for legacy __-joined cross-validation pair keys",
    "verbs": [
        "--path <file.md>",
        "--all",
        "--baseline",
    ],
    "flags": ["--path", "--all", "--baseline", "--workspace"],
}


_DEFAULT_REGEX = r"[a-z_]+_md__[a-z_]+_md"
_PAIR_KEY_RE = re.compile(r"\b[a-z_]+_md__[a-z_]+_md\b")
_DEFAULT_REMEDIATION_COMMAND = (
    "review_quality/print-pair-keys.py --type {review_type}"
)

lint_file = make_literal_lint(
    rule_key="pair_key_literals",
    default_regex=_DEFAULT_REGEX,
    fallback_regex=_PAIR_KEY_RE,
    remediation_key="replacement_command",
    default_remediation=_DEFAULT_REMEDIATION_COMMAND,
    violation_kind="pair_key_literal",
    message_template=(
        "Legacy ``__``-joined pair key {match!r} — use the canonical "
        "``_x_`` form printed by `.spec-workflow/sdd {remediation}`."
    ),
)


def main() -> None:
    run_skill_md_lint(
        rule_label="pair-key-literal",
        lint_file=lint_file,
        include_references=True,
        script_name="internal_lints/skill_md_pair_key_literals.py",
    )


if __name__ == "__main__":
    cli.run_main(main)
