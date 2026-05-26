#!/usr/bin/env python3
"""Lint reference docs for hardcoded ``/tmp/<name>-assessment.json`` literals.

Canonical staging lives under ``<doc-dir>/.sdd-state/review-assessment-staging.json``
(``sdd_core.transient_state.STAGING_FILENAME`` +
``review.pipeline_phases.resolvers.resolve_staging_path()``).

Usage:
  internal_lints/skill_md_assessment_staging_literals.py --path <file.md>
  internal_lints/skill_md_assessment_staging_literals.py --all
  internal_lints/skill_md_assessment_staging_literals.py --baseline
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re

from sdd_core import cli
from internal_lints._skill_md_lint_cli import make_literal_lint, run_skill_md_lint

__sdd_manifest__ = {
    "summary": "Lint for hardcoded /tmp/*assessment.json literals",
    "verbs": [
        "--path <file.md>",
        "--all",
        "--baseline",
    ],
    "flags": ["--path", "--all", "--baseline", "--workspace"],
}


_DEFAULT_REGEX = r"/tmp/[a-z0-9-]*assessment[a-z0-9_.-]*\.json"
_STAGING_RE = re.compile(_DEFAULT_REGEX)
_DEFAULT_REMEDIATION = (
    "Use <doc-dir>/.sdd-state/review-assessment-staging.json. See "
    "$SKILLS/sdd-common/references/quality-artifact-base.md § Run "
    "Command for the canonical recipe."
)

lint_file = make_literal_lint(
    rule_key="assessment_staging_literals",
    default_regex=_DEFAULT_REGEX,
    fallback_regex=_STAGING_RE,
    remediation_key="replacement_reference",
    default_remediation=_DEFAULT_REMEDIATION,
    violation_kind="assessment_staging_literal",
    message_template="Hardcoded staging literal {match!r}. {remediation}",
)


def main() -> None:
    run_skill_md_lint(
        rule_label="assessment-staging-literal",
        lint_file=lint_file,
        include_references=True,
        script_name=(
            "internal_lints/skill_md_assessment_staging_literals.py"
        ),
    )


if __name__ == "__main__":
    cli.run_main(main)
