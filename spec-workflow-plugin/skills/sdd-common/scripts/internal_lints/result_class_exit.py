#!/usr/bin/env python3
"""Lint: forbid ``output.error(... exit_code=1)`` on result-class outcomes.

Result-class outcomes (search miss, partial coverage, preflight gate)
must exit 0 and travel in the JSON envelope under ``data.outcome``.
A non-zero exit cancels parallel-batch siblings — see Theme D in
`docs/sdd-review-execution-resilience-plan.md`.

Heuristic: an ``output.error(...)`` call whose first argument is a
string literal containing a result-class phrase is a migration target.
Calls that already pass the runtime through ``ExitClass`` or use
``output.miss`` / ``output.partial`` / ``output.preflight_required``
are clean by construction.

Usage:
  result_class_exit.py            — scan and diff against baseline.
  result_class_exit.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints.base import LintSpec
from sdd_core import cli
from sdd_core.data_loader import load_yaml_phrase_set
from sdd_core.matchers import WordMatcher

from internal_lints._dispatch import rule_id_for

_RULE_ID = rule_id_for(__name__, __file__)

_PHRASES = load_yaml_phrase_set("result_class_phrases.yaml", key="phrases")
if not _PHRASES:
    raise RuntimeError(
        "result_class_phrases.yaml empty or PyYAML unavailable; "
        "single-source phrase load failed"
    )
_RESULT_CLASS_PHRASES = WordMatcher(_PHRASES, boundary="none")


def _is_output_error(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "error":
        value = func.value
        if isinstance(value, ast.Name) and value.id == "output":
            return True
    return False


def _first_arg_string(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, ast.JoinedStr):
        parts: list[str] = []
        for v in first.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
        return "".join(parts) if parts else None
    return None


def _exit_code(node: ast.Call) -> "int | None":
    for kw in node.keywords:
        if kw.arg != "exit_code":
            continue
        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
            return kw.value.value
    return None


_RECOVERY_KWARG_NAMES: frozenset[str] = frozenset(
    {"next_action_command_sequence"},
)


def _dict_carries_recovery_key(value: ast.Dict) -> bool:
    """True when *value* declares a recovery-sequence key in a dict literal."""
    for key_node in value.keys:
        if (
            isinstance(key_node, ast.Constant)
            and isinstance(key_node.value, str)
            and key_node.value in _RECOVERY_KWARG_NAMES
        ):
            return True
    return False


def _module_dict_carries_recovery(name: str, module_tree: ast.AST) -> bool:
    """True when a module-scope assignment ``name = {...}`` carries a recovery key.

    Walks ``ast.Assign`` and ``ast.AnnAssign`` nodes at module scope so
    a context variable referenced via ``context=ctx_dict`` resolves to
    the literal payload it was bound from. Coverage is best-effort —
    nested or mutated dicts are not chased; the role constructor
    ``output.recoverable_miss`` remains the structural fence.
    """
    for node in ast.walk(module_tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        if not isinstance(value, ast.Dict):
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                if _dict_carries_recovery_key(value):
                    return True
    return False


def _carries_recovery_sequence(
    node: ast.Call,
    module_tree: "ast.AST | None" = None,
) -> bool:
    """Return True when an ``output.error(...)`` call passes a recovery sequence.

    Inverse of the result-class rule: an envelope carrying
    ``next_action_command_sequence`` MUST be result-class. The walk
    covers three AST patterns so the structural fence catches every
    drift mode the role constructor (``output.recoverable_miss``) is
    meant to enforce:

    1. **Direct kwarg.** ``output.error(..., next_action_command_sequence=...)``
       — captured by inspecting ``node.keywords``.
    2. **Dict-literal context.** ``output.error(..., context={"next_action_command_sequence": ...})``
       — captured by walking the literal dict's keys.
    3. **Context variable.** ``output.error(..., context=ctx)`` where
       ``ctx`` is bound at module scope to a dict literal carrying the
       recovery key — captured by resolving the name against the module
       AST when *module_tree* is supplied.
    """
    for kw in node.keywords:
        if kw.arg in _RECOVERY_KWARG_NAMES:
            return True
        if kw.arg == "context":
            if isinstance(kw.value, ast.Dict) and _dict_carries_recovery_key(
                kw.value,
            ):
                return True
            if (
                isinstance(kw.value, ast.Name)
                and module_tree is not None
                and _module_dict_carries_recovery(kw.value.id, module_tree)
            ):
                return True
    return False


class ResultClassExitChecker:
    """Flag ``output.error(... exit_code=1)`` on result-class messages."""

    rule_id = _RULE_ID
    severity = "error"

    def __init__(self) -> None:
        self._module_path: "Path | None" = None
        self._module_tree: "ast.AST | None" = None

    def _module_tree_for(self, path: Path) -> "ast.AST | None":
        if path == self._module_path:
            return self._module_tree
        self._module_path = path
        try:
            self._module_tree = ast.parse(
                path.read_text(encoding="utf-8"), filename=str(path),
            )
        except (OSError, SyntaxError):
            self._module_tree = None
        return self._module_tree

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        if not isinstance(node, ast.Call) or not _is_output_error(node):
            return
        module_tree = self._module_tree_for(path)
        # Inverse rule — envelope carrying
        # ``next_action_command_sequence`` is structurally result-class.
        if _carries_recovery_sequence(node, module_tree=module_tree):
            yield LintFinding(
                rule_id=self.rule_id,
                severity=self.severity,
                file=str(path),
                line=node.lineno,
                message=(
                    "output.error carries `next_action_command_sequence` — "
                    "replace with output.recoverable_miss (the only "
                    "constructor for the recoverable-miss role; emits "
                    "result-class envelopes that route through the "
                    "agent's recovery surface)."
                ),
            )
            return
        exit_code = _exit_code(node)
        # Default exit_code on output.error is 1 — flag whenever it's
        # 1 (explicit or implicit) and the message is result-class.
        if exit_code not in (None, 1):
            return
        message = _first_arg_string(node)
        if not message:
            return
        if message not in _RESULT_CLASS_PHRASES:
            return
        yield LintFinding(
            rule_id=self.rule_id,
            severity=self.severity,
            file=str(path),
            line=node.lineno,
            message=(
                "output.error on a result-class outcome — replace with "
                "output.miss / output.partial / output.preflight_required "
                "(exit 0 with data.outcome)."
            ),
        )


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    checkers=(ResultClassExitChecker(),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
