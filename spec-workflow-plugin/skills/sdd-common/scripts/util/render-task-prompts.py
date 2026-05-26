#!/usr/bin/env python3
"""Render the canonical task-prompt prefix + 4-step lifecycle suffix.

Reads the programmatic constants from :mod:`sdd_core.task_prompts`
and prints them for a given ``--target``. Mirrors the
``review_quality/print-pair-keys.py`` pattern: narrative references
(``prompt-suffix-canonical.md``) quote this script instead of
restating the literal strings. Single source of truth guarantees the
author-facing doc, the ``tasks-template.md`` defaults, and
``spec/lint-tasks.py`` never drift.

Usage:
  .spec-workflow/sdd util/render-task-prompts.py --target demo              # prefix + suffix
  .spec-workflow/sdd util/render-task-prompts.py --target demo --json       # JSON envelope

Exit code: 0 always (result in JSON envelope when ``--json``).
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, output
from sdd_core.task_prompts import (
    render_task_lifecycle_suffix,
    render_task_prompt_prefix,
)


__sdd_manifest__ = {
    "summary": "Render canonical task-prompt prefix + 4-step lifecycle suffix",
    "verbs": ["--target <spec-name>"],
    "aliases": {},
    "flags": ["--target", "--json"],
}


def main() -> None:
    parser = cli.strict_parser(__doc__)
    cli.target_argument(parser, family="spec")
    parser.add_argument(
        "--json", action="store_true",
        help="Emit as a JSON envelope instead of plain text.",
    )
    args = parser.parse_args()

    prefix = render_task_prompt_prefix(args.spec_name)
    suffix = render_task_lifecycle_suffix(args.spec_name)

    if args.json:
        output.success(
            {"prefix": prefix, "suffix": suffix, "spec_name": args.spec_name},
            f"Rendered task-prompt scaffolding for {args.spec_name!r}",
        )
        return

    print(prefix.rstrip())
    print(suffix.strip())


if __name__ == "__main__":
    cli.run_main(main)
