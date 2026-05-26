#!/usr/bin/env python3
"""Lint: emitted command literals must be argparse-parseable.

Every emitter in ``sdd_core.command_templates.__all__`` is rendered
against its declared fixture and the resulting argv is validated by
the target script's argparse. Why: parent-parser flags emitted after
the subcommand token fall into the subparser's argv slice and
trigger ``required: --target`` — a regression class that landed
silently in the past. This lint blocks the entire class on day one.

Usage:
  internal_lints/emitted_commands_parse.py            — scan + diff baseline
  internal_lints/emitted_commands_parse.py --refresh  — rewrite baseline
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import shlex
from pathlib import Path
from typing import Any, Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints.base import LintSpec
from internal_lints._dispatch import rule_id_for
from sdd_core import cli, command_templates
from sdd_core.data_loader import load_yaml

_RULE_ID = rule_id_for(__name__, __file__)
_FIXTURE_FILE = "emitter_fixtures.yaml"
_SHIM_PREFIX = ".spec-workflow/sdd"


def _load_fixtures() -> dict[str, dict[str, Any]]:
    """Return {emitter_name: fixture_row} from the canonical YAML.

    Empty mapping when PyYAML / file is missing — the lint then
    reports every emitter as missing a fixture (loud failure).
    """
    payload = load_yaml(_FIXTURE_FILE)
    raw = payload.get("emitters") if isinstance(payload, dict) else {}
    if not isinstance(raw, dict):
        return {}
    return {name: row for name, row in raw.items() if isinstance(row, dict)}


def _emitter_names() -> tuple[str, ...]:
    return tuple(
        name for name in getattr(command_templates, "__all__", ())
        if name.startswith("build_")
    )


def _check_fixture(name: str, row: dict[str, Any]) -> Iterable[LintFinding]:
    """Yield findings when *row* describes a non-parseable literal.

    Validates: (a) the dispatch script matches ``expected_dispatch_script``,
    (b) declared ``parent_only_flags`` precede any positional (subcommand)
    token in the rendered argv, (c) the emitter actually ran without
    raising. Skips emitters opted out via ``skip:``.
    """
    if "skip" in row:
        return
    builder = getattr(command_templates, name, None)
    if builder is None:
        yield LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=str(_fixture_path()), line=1,
            message=(
                f"Fixture lists emitter {name!r} but command_templates "
                "exports no such name."
            ),
        )
        return
    kwargs = dict(row.get("kwargs") or {})
    try:
        rendered = builder(**kwargs)
    except Exception as exc:  # pragma: no cover — render is the gate
        yield LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=str(_fixture_path()), line=1,
            message=f"{name!r} raised on render: {exc!r}",
        )
        return
    if not isinstance(rendered, str):
        yield LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=str(_fixture_path()), line=1,
            message=(
                f"{name!r} returned {type(rendered).__name__}, not str — "
                "declare skip: in the fixture if this is intentional."
            ),
        )
        return
    argv = shlex.split(rendered)
    if len(argv) < 2 or argv[0] != _SHIM_PREFIX:
        yield LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=str(_fixture_path()), line=1,
            message=(
                f"{name!r}: rendered literal does not start with "
                f"{_SHIM_PREFIX!r} — got {rendered!r}"
            ),
        )
        return
    expected = row.get("expected_dispatch_script")
    if expected and argv[1] != expected:
        yield LintFinding(
            rule_id=_RULE_ID, severity="error",
            file=str(_fixture_path()), line=1,
            message=(
                f"{name!r}: dispatch script {argv[1]!r} != "
                f"expected {expected!r}"
            ),
        )
    parent_only = row.get("parent_only_flags") or ()
    if parent_only:
        # Find the first non-flag positional token after the script
        # path — this is the subcommand. Parent-only flags must appear
        # before it; argparse refuses them otherwise.
        first_positional = None
        i = 2
        while i < len(argv):
            tok = argv[i]
            if tok.startswith("--"):
                # Skip the flag and its value (heuristic: next token if
                # it does not itself start with --). Bare switches
                # without values still advance by 1.
                i += 1
                if i < len(argv) and not argv[i].startswith("--"):
                    i += 1
                continue
            first_positional = i
            break
        for flag in parent_only:
            if flag not in argv:
                yield LintFinding(
                    rule_id=_RULE_ID, severity="error",
                    file=str(_fixture_path()), line=1,
                    message=(
                        f"{name!r}: parent-only flag {flag!r} missing "
                        f"from rendered argv {rendered!r}"
                    ),
                )
                continue
            flag_pos = argv.index(flag)
            if first_positional is not None and flag_pos > first_positional:
                yield LintFinding(
                    rule_id=_RULE_ID, severity="error",
                    file=str(_fixture_path()), line=1,
                    message=(
                        f"{name!r}: parent-only flag {flag!r} appears at "
                        f"index {flag_pos} but the subcommand "
                        f"{argv[first_positional]!r} is at index "
                        f"{first_positional}. Argparse subparsers do not "
                        "see parent flags written after the subcommand "
                        "token. Route the flag through "
                        "build_shim_command(parent_flags={...}) instead."
                    ),
                )


def _fixture_path() -> Path:
    from sdd_core.data_loader import DATA_DIR
    return DATA_DIR / _FIXTURE_FILE


class _EmitterChecker:
    """Path-mode checker — runs once per scan, ignores its argument."""

    severity = "error"
    rule_id = _RULE_ID
    _ran = False

    def check_path(self, path: Path) -> Iterable[LintFinding]:
        # Only run once per LintSpec walk — the spec lists a single
        # path root so we just gate on `_ran` to avoid duplicates.
        if self._ran:
            return ()
        self._ran = True
        fixtures = _load_fixtures()
        emitters = _emitter_names()
        findings: list[LintFinding] = []
        # Every emitter must have a fixture row (or be opted out).
        for name in emitters:
            if name not in fixtures:
                findings.append(LintFinding(
                    rule_id=_RULE_ID, severity="error",
                    file=str(_fixture_path()), line=1,
                    message=(
                        f"Emitter {name!r} has no fixture row in "
                        f"{_FIXTURE_FILE}. Add kwargs / "
                        "expected_dispatch_script (or skip: '<reason>')."
                    ),
                ))
                continue
            findings.extend(_check_fixture(name, fixtures[name]))
        # Stale fixture rows (no matching emitter) — surface as well.
        for name in fixtures:
            if name not in emitters:
                findings.append(LintFinding(
                    rule_id=_RULE_ID, severity="error",
                    file=str(_fixture_path()), line=1,
                    message=(
                        f"Fixture {name!r} has no matching "
                        "command_templates emitter. Drop the row."
                    ),
                ))
        return findings


SPEC = LintSpec(
    rule_id=_RULE_ID,
    # The lint reads a single fixture file; the root just anchors
    # the LintSpec walk so the runner has something to enumerate.
    roots=(".cursor/skills/sdd-common/scripts/sdd_core/data",),
    path_checkers=(_EmitterChecker(),),
    file_glob=_FIXTURE_FILE,
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
