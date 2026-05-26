#!/usr/bin/env python3
"""Lint: forbid Python 3.10+-only constructs that broke E1/E8.

Flags ``@dataclass(... slots=True ...)`` decorators and the other
3.10+-only features the codebase deliberately avoids
(``match`` statements, ``typing.Self``, ``asyncio.TaskGroup``,
``ExceptionGroup``). Driving them out of the codebase keeps the
repo runnable on the macOS-default Python 3.9.

Usage:
  no_dataclass_slots.py            — scan and diff against baseline.
  no_dataclass_slots.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints.base import LintSpec
from sdd_core import cli

from internal_lints._dispatch import rule_id_for

_RULE_ID = rule_id_for(__name__, __file__)
_TYPING_SELF_NAMES = frozenset({"Self"})
_MATCH_CLS = getattr(ast, "Match", None)


def _is_dataclass_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "dataclass":
        return True
    if isinstance(func, ast.Name) and func.id == "dataclass":
        return True
    return False


def _is_dataclass_slots_true(node: ast.AST) -> bool:
    if not isinstance(node, ast.ClassDef):
        return False
    for deco in node.decorator_list:
        if not _is_dataclass_call(deco):
            continue
        for kw in deco.keywords:
            if (
                kw.arg == "slots"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            ):
                return True
    return False


def _dataclass_slots_lineno(node: ast.AST) -> int:
    assert isinstance(node, ast.ClassDef)
    for deco in node.decorator_list:
        if _is_dataclass_call(deco):
            return deco.lineno
    return node.lineno


def _is_match_stmt(node: ast.AST) -> bool:
    return _MATCH_CLS is not None and isinstance(node, _MATCH_CLS)


def _is_typing_self_attr(node: ast.AST) -> bool:
    if not isinstance(node, ast.Attribute):
        return False
    value = node.value
    return (
        isinstance(value, ast.Name)
        and value.id == "typing"
        and node.attr in _TYPING_SELF_NAMES
    )


def _is_typing_self_import(node: ast.AST) -> bool:
    if not isinstance(node, ast.ImportFrom) or node.module != "typing":
        return False
    return any(alias.name in _TYPING_SELF_NAMES for alias in node.names)


def _is_asyncio_taskgroup(node: ast.AST) -> bool:
    if not isinstance(node, ast.Attribute) or node.attr != "TaskGroup":
        return False
    value = node.value
    return isinstance(value, ast.Name) and value.id == "asyncio"


def _is_exception_group(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "ExceptionGroup"


@dataclass(frozen=True)
class _NodeRule:
    predicate: Callable[[ast.AST], bool]
    rule_id: str
    message: str
    lineno: Callable[[ast.AST], int] = lambda n: n.lineno  # noqa: E731


_RULES: tuple[_NodeRule, ...] = (
    _NodeRule(
        predicate=_is_dataclass_slots_true,
        rule_id=_RULE_ID,
        message=(
            "@dataclass(slots=True) is Python 3.10+ — "
            "drop slots=True; frozen=True still gives the "
            "immutability contract on Python 3.9."
        ),
        lineno=_dataclass_slots_lineno,
    ),
    _NodeRule(
        predicate=_is_match_stmt,
        rule_id="no-match-stmt",
        message=(
            "match/case is Python 3.10+ — replace with an "
            "equivalent if/elif chain or registry dispatch."
        ),
    ),
    _NodeRule(
        predicate=_is_typing_self_attr,
        rule_id="no-typing-self",
        message=(
            "typing.Self is Python 3.11+ — annotate with "
            "the explicit class name in a string literal."
        ),
    ),
    _NodeRule(
        predicate=_is_typing_self_import,
        rule_id="no-typing-self",
        message=(
            "typing.Self is Python 3.11+ — drop the "
            "import and use the class name directly."
        ),
    ),
    _NodeRule(
        predicate=_is_asyncio_taskgroup,
        rule_id="no-taskgroup",
        message=(
            "asyncio.TaskGroup is Python 3.11+ — "
            "use asyncio.gather or a manual loop."
        ),
    ),
    _NodeRule(
        predicate=_is_exception_group,
        rule_id="no-taskgroup",
        message=(
            "ExceptionGroup is Python 3.11+ — raise individual "
            "exceptions or aggregate via a list."
        ),
    ),
)


class _PredicateChecker:
    """Yield findings for the first matching :class:`_NodeRule`."""

    severity = "error"
    rule_id = _RULE_ID

    def __init__(self, rules: tuple[_NodeRule, ...]) -> None:
        self._rules = rules

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]:
        for rule in self._rules:
            if rule.predicate(node):
                yield LintFinding(
                    rule_id=rule.rule_id,
                    severity=self.severity,
                    file=str(path),
                    line=rule.lineno(node),
                    message=rule.message,
                )


SPEC = LintSpec(
    rule_id=_RULE_ID,
    roots=(".cursor/skills",),
    checkers=(_PredicateChecker(_RULES),),
)


analyze = SPEC.analyze
compare_baseline = SPEC.compare_baseline


def main() -> None:
    _base.run_lint_cli(SPEC)


if __name__ == "__main__":
    cli.run_main(main)
