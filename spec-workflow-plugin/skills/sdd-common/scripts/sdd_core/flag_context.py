"""Per-script-group flag-context registry for cross-script ``did_you_mean`` hints.

When an agent reaches for a flag canonical on a sibling script in the
same group (e.g. ``--category`` is canonical on ``review/pipeline-tick.py``,
``approval/request.py``, ``util/detect-doc-state.py`` but not on
``review/check-template-compliance.py``), ``_emit_unknown_flag_warn``
consults this registry to surface a diagnostic line naming the
sibling scripts that *do* accept the flag. The registry is auto-built
at first-call time by reflecting on every executable script under
``.spec-workflow/sdd {group}/`` — no hand-maintained table.

Single owner: this module. Single caller: ``sdd_core.cli._sibling_flag_hint``.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from . import paths

__all__ = ["sibling_flag_acceptance_dict", "scripts_root"]


def scripts_root() -> "Path | None":
    """Return the on-disk ``.spec-workflow/sdd`` scripts root or ``None``.

    Resolves via :func:`sdd_core.paths.find_workflow_root` so the
    detection mirrors every other path-aware helper. Returns ``None``
    when the workflow root is not reachable so callers branch on a
    typed absence rather than on a misleading stub path.
    """
    try:
        wf_root = paths.find_workflow_root()
    except Exception:
        return None
    candidate = Path(wf_root) / ".spec-workflow" / "sdd"
    if candidate.is_dir():
        return candidate
    return None


@lru_cache(maxsize=None)
def _sibling_flag_acceptance_frozen(
    group: str,
) -> "frozenset[tuple[str, frozenset[str]]]":
    """Cached frozenset form of the registry — internal hashable cache key."""
    return frozenset(_compute_sibling_flag_acceptance(group).items())


def sibling_flag_acceptance_dict(group: str) -> dict[str, frozenset[str]]:
    """Return ``{flag: frozenset(scripts_that_accept_it)}`` for *group* (cached).

    Single public entry point for the registry; the frozenset cache
    behind :func:`_sibling_flag_acceptance_frozen` amortises the AST
    reflection cost across the agent session.
    """
    return dict(_sibling_flag_acceptance_frozen(group))


def _compute_sibling_flag_acceptance(group: str) -> dict[str, frozenset[str]]:
    """Walk *group*'s scripts and reflect their parsers (uncached path)."""
    root = scripts_root()
    if root is None:
        return {}
    group_dir = root / group
    if not group_dir.is_dir():
        return {}
    acceptance: dict[str, set[str]] = {}
    for script in sorted(group_dir.glob("*.py")):
        if script.name.startswith("_"):
            continue
        try:
            flags = _reflect_flags(script)
        except Exception:
            continue
        for flag in flags:
            acceptance.setdefault(flag, set()).add(script.name)
    return {k: frozenset(v) for k, v in acceptance.items()}


def _iter_add_argument_calls(tree: ast.AST) -> Iterable[ast.Call]:
    """Yield every ``Call`` node that looks like ``parser.add_argument(...)``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "add_argument":
            yield node


def _option_strings_from_call(call: ast.Call) -> list[str]:
    """Extract ``--flag`` literals from a ``parser.add_argument`` call.

    Walks positional args, picks string constants starting with ``-``.
    Skips dynamic / non-literal values; the registry is best-effort —
    a script that builds its parser from runtime values simply
    contributes fewer hints.
    """
    out: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            v = arg.value
            if v.startswith("-"):
                out.append(v)
    return out


def _reflect_flags(script: Path) -> frozenset[str]:
    """Return the set of ``option_strings`` declared on *script*'s parser.

    Uses a static AST scan rather than importing the script — many
    scripts run side-effects at import time (workspace chdir, output
    emission) that would interfere with a hot-path lookup. Scripts
    that opt into a sentinel ``__sdd_known_flags__`` module attribute
    short-circuit the AST walk; the module-level constant wins so
    scripts with dynamic parsers stay representable.
    """
    try:
        text = script.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    try:
        tree = ast.parse(text, filename=str(script))
    except SyntaxError:
        return frozenset()
    sentinel = _read_module_constant(tree, "__sdd_known_flags__")
    if sentinel is not None:
        return frozenset(sentinel)
    flags: set[str] = set()
    for call in _iter_add_argument_calls(tree):
        flags.update(_option_strings_from_call(call))
    return frozenset(flags)


def _read_module_constant(tree: ast.AST, name: str) -> "list[str] | None":
    """Return the literal string list assigned to *name* at module scope."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return _coerce_string_iterable(node.value)
        elif isinstance(node, ast.AnnAssign):
            tgt = node.target
            if (
                isinstance(tgt, ast.Name)
                and tgt.id == name
                and node.value is not None
            ):
                return _coerce_string_iterable(node.value)
    return None


def _coerce_string_iterable(value: ast.AST) -> "list[str] | None":
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        out: list[str] = []
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
        return out
    return None
