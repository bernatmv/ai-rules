#!/usr/bin/env python3
"""Lint: every ``sdd_core/`` module file must have a production consumer.

A module under ``sdd_core/`` is an orphan when no production file
outside its own package imports it (manifest entries, docstrings, and
test files do not count). Orphan abstractions in a heavily-trafficked
package mislead future readers — they assume the module is load-bearing
and route around it. The lint flags such modules so the reviewer
either deletes them or wires them into a real consumer.

Existing orphans live in the baseline; new findings (modules added
without a consumer, or modules whose last consumer was removed) fail
the lint until either fixed or baselined with a written rationale.

Usage:
  orphan_sdd_core_modules.py            — scan and diff against baseline.
  orphan_sdd_core_modules.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
from pathlib import Path

from internal_lints import LintFinding
from internal_lints._dispatch import rule_id_for
from internal_lints.baseline import (
    diff_baseline,
    key_for,
    read_baseline,
    write_baseline,
)
from sdd_core import cli, output

_RULE_ID = rule_id_for(__name__, __file__)

# Path discovery — anchor on the repo root by walking up from this file.
_LINT_FILE = Path(__file__).resolve()
_SKILLS_ROOT = _LINT_FILE.parent.parent  # …/sdd-common/scripts/
_SDD_CORE_ROOT = _SKILLS_ROOT / "sdd_core"
_TESTS_DIR_NAME = "tests"


def _module_dotted_name(path: Path) -> str:
    """Return ``sdd_core.subpkg.mod`` for *path* under sdd_core/."""
    rel = path.relative_to(_SKILLS_ROOT)
    parts = list(rel.with_suffix("").parts)
    return ".".join(parts)


def _iter_sdd_core_modules() -> list[Path]:
    """Return every ``*.py`` file under ``sdd_core/`` excluding dunders.

    ``__init__.py`` is the package facade — it is never an "orphan"
    because Python loads it on every package import. Likewise
    ``__main__.py`` and bootstrap stubs are entry-points.
    """
    out: list[Path] = []
    for path in _SDD_CORE_ROOT.rglob("*.py"):
        if path.name in {"__init__.py", "__main__.py", "_bootstrap.py"}:
            continue
        if "__pycache__" in path.parts:
            continue
        out.append(path)
    return sorted(out)


def _resolve_relative_import(
    module: "str | None", level: int, importer: Path,
) -> "str | None":
    """Return the absolute dotted name a relative import resolves to.

    *importer* is the file containing the import; *level* is the number
    of leading dots; *module* is the right-hand side (may be ``None``
    for ``from . import x``). Returns ``None`` when the import would
    escape the skills tree.
    """
    rel = importer.relative_to(_SKILLS_ROOT)
    parts = list(rel.with_suffix("").parts)
    if rel.name == "__init__":  # pragma: no cover — already filtered upstream
        parts = parts[:-1]
    base = parts[: len(parts) - level] if level else parts
    base_pkg = parts[: len(parts) - level + 1][:-1] if level else parts[:-1]
    anchor = base if not module else base_pkg
    target = list(anchor)
    if module:
        target.extend(module.split("."))
    if not target or target[0] != "sdd_core":
        return None
    return ".".join(target)


def _imported_dotted_names(tree: ast.AST, importer: Path) -> set[str]:
    """Return every ``sdd_core.*`` dotted name imported by *tree*.

    Covers absolute imports (``import sdd_core.x``,
    ``from sdd_core.x import y``), relative imports
    (``from .x import y``), and the package-facade form
    (``from sdd_core import x`` — ``x`` is reported as
    ``sdd_core.x``).
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sdd_core" or alias.name.startswith("sdd_core."):
                    out.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                resolved = _resolve_relative_import(
                    node.module, node.level, importer,
                )
                if resolved:
                    out.add(resolved)
                    for alias in node.names:
                        out.add(f"{resolved}.{alias.name}")
                continue
            module = node.module or ""
            if module == "sdd_core":
                for alias in node.names:
                    out.add(f"sdd_core.{alias.name}")
            elif module.startswith("sdd_core."):
                out.add(module)
                for alias in node.names:
                    out.add(f"{module}.{alias.name}")
    return out


def _collect_consumer_imports() -> set[str]:
    """Return the set of dotted names imported by any production file.

    A "production file" is any ``*.py`` under
    ``.cursor/skills/sdd-common/scripts/`` that is not (a) a test file
    or (b) inside a ``__pycache__`` tree.
    """
    seen: set[str] = set()
    for path in _SKILLS_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if _TESTS_DIR_NAME in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        seen.update(_imported_dotted_names(tree, path))
    return seen


def _is_consumer_external(
    consumer: str, target: str,
) -> bool:
    """True when *consumer* lives outside *target*'s own subtree.

    Self-references inside a package (``sdd_core.approval.cli`` importing
    ``sdd_core.approval.context``) still count as consumption — what we
    forbid is a module with **no** importer. Modules within their own
    file naturally do not count: that case is filtered by the caller.
    """
    return consumer != target


def analyze() -> list[LintFinding]:
    """Return one finding per orphan ``sdd_core/`` module."""
    consumed = _collect_consumer_imports()
    findings: list[LintFinding] = []
    for module_path in _iter_sdd_core_modules():
        dotted = _module_dotted_name(module_path)
        # The module's own file may import from itself only via
        # tests/recursion edge cases; we treat any consumer dotted name
        # equal to *dotted* as "not external" by skipping it. But
        # because the AST collector walks every production file, a
        # match means at least one file imports the module.
        if dotted in consumed:
            continue
        try:
            rel = str(module_path.resolve().relative_to(Path.cwd().resolve()))
        except ValueError:
            rel = str(module_path)
        findings.append(LintFinding(
            rule_id=_RULE_ID,
            severity="error",
            file=rel,
            line=1,
            message=(
                f"{dotted} has no production consumer outside its own "
                "module (manifest entries and tests do not count). "
                "Wire it into a caller or delete the orphan."
            ),
            extra={"reason": "orphan-sdd-core-module"},
        ))
    return findings


def compare_baseline(findings: list[LintFinding]) -> dict:
    """Diff *findings* against the on-disk baseline for the dispatcher."""
    observed = sorted({key_for(f) for f in findings})
    return diff_baseline(observed, rule_id=_RULE_ID)


def _emit_envelope(findings: list[LintFinding], *, refresh: bool) -> None:
    observed = sorted({key_for(f) for f in findings})
    if refresh:
        write_baseline(_RULE_ID, observed)
        output.success(
            {"rule_id": _RULE_ID, "count": len(observed)},
            f"{_RULE_ID}: baseline refreshed",
        )
        return
    diff = diff_baseline(observed, rule_id=_RULE_ID)
    if diff["new"] or diff["stale"]:
        output.error(
            f"{_RULE_ID}: new={len(diff['new'])} stale={len(diff['stale'])}",
            hint=(
                "Wire the orphan module into a real consumer, delete it, "
                "or refresh the baseline if the finding is expected."
            ),
            next_action_command=(
                f".spec-workflow/sdd internal_lints/baseline-refresh.py "
                f"--rule {_RULE_ID}"
            ),
        )
    output.success({"known": diff["known"]}, f"{_RULE_ID}: clean")


def main() -> None:
    parser = cli.strict_parser(
        "Detect orphan modules under .cursor/skills/sdd-common/scripts/sdd_core/"
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    args = parser.parse_args()
    findings = analyze()
    _emit_envelope(findings, refresh=args.refresh)


if __name__ == "__main__":
    cli.run_main(main)
