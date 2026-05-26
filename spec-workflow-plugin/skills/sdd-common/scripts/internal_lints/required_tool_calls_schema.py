#!/usr/bin/env python3
"""Lint: ``required_tool_calls`` payloads must round-trip the typed schema.

Every dict literal whose key set looks like a ``required_tool_calls``
payload (``kind`` + ``harness_tool`` + ``args``) is checked against
:class:`sdd_core.required_tool_calls.RequiredToolCallsPayload`. Drift
modes the lint catches:

* legacy ``tool: "TodoWrite"`` field at the top level (the dual-channel
  shape we want to keep out of new payloads)
* ``args.todos`` instead of ``args.lifecycle_mirror`` (the field-name
  rename the dataclass enforces)
* missing ``consumer`` (``"agent"`` vs ``"harness_adapter"``) — the
  routing decision must be on the wire, not inferred at the harness
  adapter

Empty baseline by default — the dataclass is the structural fence and
this lint guards against future drift. New violations fail CI; existing
emit sites can opt into the dataclass progressively.

Usage:
  required_tool_calls_schema.py            — scan and diff against baseline.
  required_tool_calls_schema.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints._dispatch import rule_id_for
from internal_lints.base import LintSpec
from sdd_core import cli

_RULE_ID = rule_id_for(__name__, __file__)

_PAYLOAD_KEY_HINTS: frozenset[str] = frozenset(
    {"kind", "harness_tool", "harness_name", "consumer", "args"},
)
_FORBIDDEN_TOP_LEVEL: frozenset[str] = frozenset({"tool", "todos"})
_FORBIDDEN_ARGS_KEYS: frozenset[str] = frozenset({"todos"})


def _string_keys(node: ast.Dict) -> set[str]:
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return keys


def _looks_like_required_tool_calls(node: ast.Dict) -> bool:
    """Return True when the dict has the required_tool_calls shape.

    Match heuristic: the dict declares ``kind`` + ``harness_tool`` (or
    ``args`` with a ``todos`` / ``lifecycle_mirror`` value). Avoids
    false-positives on advisory dicts and prompt-template dicts that
    share a single key with the wire shape.
    """
    keys = _string_keys(node)
    if {"kind", "harness_tool"}.issubset(keys):
        return True
    if "args" in keys and ("todos" in keys or "lifecycle_mirror" in keys):
        return True
    return False


def _value_for(node: ast.Dict, key: str) -> "ast.AST | None":
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return v
    return None


class RequiredToolCallsSchemaChecker:
    """Flag ``required_tool_calls`` dicts that drift from the dataclass shape."""

    rule_id = _RULE_ID
    severity = "error"

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if not isinstance(node, ast.Dict):
            return ()
        if not _looks_like_required_tool_calls(node):
            return ()
        keys = _string_keys(node)
        line = getattr(node, "lineno", 1)
        forbidden_top = sorted(keys & _FORBIDDEN_TOP_LEVEL)
        if forbidden_top:
            return (LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=line,
                message=(
                    f"required_tool_calls payload carries forbidden "
                    f"top-level keys {forbidden_top!r}; construct via "
                    "sdd_core.required_tool_calls.RequiredToolCallsPayload."
                ),
            ),)
        if not _PAYLOAD_KEY_HINTS.issubset(keys):
            missing = sorted(_PAYLOAD_KEY_HINTS - keys)
            return (LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=line,
                message=(
                    f"required_tool_calls payload missing required keys "
                    f"{missing!r}; construct via "
                    "sdd_core.required_tool_calls.RequiredToolCallsPayload."
                ),
            ),)
        args_value = _value_for(node, "args")
        if isinstance(args_value, ast.Dict):
            args_keys = _string_keys(args_value)
            forbidden_args = sorted(args_keys & _FORBIDDEN_ARGS_KEYS)
            if forbidden_args:
                return (LintFinding(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    file=str(path),
                    line=line,
                    message=(
                        f"required_tool_calls.args carries forbidden keys "
                        f"{forbidden_args!r}; rename to "
                        "``lifecycle_mirror`` (see RequiredToolCallsPayload)."
                    ),
                ),)
        return ()


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    checkers=(RequiredToolCallsSchemaChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
