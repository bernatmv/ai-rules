#!/usr/bin/env python3
"""Lint recovery-command emitters under ``review/pipeline_phases/``.

Rule 1 — dispatcher hygiene: reject
``.spec-workflow/sdd review/prepare-pipeline.py --phase ...``. Emitters
target ``review/pipeline-tick.py --phase`` instead.

Rule 2 — single ack emitter: only
``launch_preconditions/types.py::build_ack_reference_read_command`` may
emit ``.spec-workflow/sdd ... --phase ack-reference-reads``.

Rule 3 — legacy-flag tokens: any emitted shim string containing
``--feature`` / ``--repo-id`` / ``--target-name`` / ``--target-repo`` /
``--project-path`` is rejected. Emitters route these through the
canonical ``--target`` / ``--workspace`` builder calls in
``sdd_core.command_templates``. Carve-outs (dispatcher locator surface
in ``approval/request.py`` and the ``update-manifest.py`` subparser) are
documented in ``tool-patterns.md`` § "Workspace Flag-Rename Carve-outs".

Usage:
  internal_lints/emitter_dispatcher_hygiene.py           # lint repo
  internal_lints/emitter_dispatcher_hygiene.py --baseline  # report only
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
import re
from pathlib import Path

from internal_lints._legacy_flags import CARVE_OUTS as _LEGACY_CARVE_OUTS
from sdd_core import cli, output, paths

__sdd_manifest__ = {
    "summary": "Enforce pipeline-tick.py + single ack-reference-reads emitter",
    "verbs": ["(no args)", "--baseline"],
    "flags": ["--baseline", "--workspace"],
}

_EMITTER_ROOT = "review/pipeline_phases"
_LEGACY_FLAG_SCAN_ROOTS = (
    "review/pipeline_phases",
    "workspace",
    "sdd_core/command_templates.py",
)
_FORBIDDEN_RE = re.compile(
    r"\.spec-workflow/sdd\s+review/prepare-pipeline\.py\s+--phase"
)
_LEGACY_FLAG_TOKENS_RE = re.compile(
    r"--(feature|repo-id|target-name|target-repo|project-path)\b"
)
_LEGACY_FLAG_CARVE_OUTS: dict[str, tuple[str, ...]] = {
    "--target-name": ("--category",),
    "--repo-id": ("workspace/update-manifest.py",),
}
_ACK_REF_ALLOWED_FILE = "launch_preconditions/types.py"
_ACK_REF_ALLOWED_FUNC = "build_ack_reference_read_command"
_ACK_REF_VERB = "--phase ack-reference-reads"
_DISPATCHER_PREFIX = ".spec-workflow/sdd"


def _walk_py(root: Path):
    return (p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _render_string_node(node: ast.AST) -> str:
    """Return the literal portion of a ``Constant`` / ``JoinedStr`` node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("")
        return "".join(parts)
    return ""


class _AckEmissionVisitor(ast.NodeVisitor):
    """Collect ``--phase ack-reference-reads`` emissions and legacy-flag
    tokens inside dispatcher-prefixed strings, with their enclosing
    function name. Does not descend into ``JoinedStr`` children so a
    single emission is not double-counted."""

    def __init__(self) -> None:
        self.emissions: list[tuple[int, str]] = []
        self.legacy_flag_emissions: list[tuple[int, str, str]] = []
        self._func_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def _check(self, node: ast.AST) -> None:
        text = _render_string_node(node)
        if _ACK_REF_VERB in text and _DISPATCHER_PREFIX in text:
            func = self._func_stack[-1] if self._func_stack else "<module>"
            self.emissions.append((getattr(node, "lineno", 0), func))
        if _DISPATCHER_PREFIX in text:
            match = _LEGACY_FLAG_TOKENS_RE.search(text)
            if match is not None:
                flag = match.group(0)
                allowed_targets = _LEGACY_FLAG_CARVE_OUTS.get(flag, ())
                if not any(target in text for target in allowed_targets):
                    func = self._func_stack[-1] if self._func_stack else "<module>"
                    self.legacy_flag_emissions.append(
                        (getattr(node, "lineno", 0), func, flag),
                    )

    def visit_Constant(self, node: ast.Constant) -> None:
        self._check(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self._check(node)


def lint_file(path: Path, *, root: Path) -> list[dict]:
    """Return one violation dict per forbidden emission."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    violations: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _FORBIDDEN_RE.search(line):
            violations.append({
                "file": str(path),
                "line": lineno,
                "snippet": line.strip(),
                "fix": (
                    "Replace 'review/prepare-pipeline.py --phase' with "
                    "'review/pipeline-tick.py --phase'"
                ),
            })
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return violations
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = path.as_posix()
    visitor = _AckEmissionVisitor()
    visitor.visit(tree)
    for lineno, func in visitor.emissions:
        allowed = (
            rel == _ACK_REF_ALLOWED_FILE
            and func == _ACK_REF_ALLOWED_FUNC
        )
        if allowed:
            continue
        violations.append({
            "file": str(path),
            "line": lineno,
            "snippet": f"{rel}:{func} emits --phase ack-reference-reads",
            "fix": (
                "Build the ack command via "
                "launch_preconditions.types.build_ack_reference_read_command "
                "(single producer for the --references name=<sha> token)."
            ),
        })
    for lineno, func, flag in visitor.legacy_flag_emissions:
        violations.append({
            "file": str(path),
            "line": lineno,
            "snippet": (
                f"{rel}:{func} emits dispatcher string with legacy flag "
                f"{flag!r}"
            ),
            "fix": (
                "Route the command through a "
                "sdd_core.command_templates.build_*_command(...) builder "
                "so emitted shim strings use --target / --workspace. "
                "See tool-patterns.md § Workspace Flag-Rename Carve-outs."
            ),
        })
    return violations


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("--baseline", "--refresh", action="store_true", dest="baseline")
    args = parser.parse_args()

    scripts_dir = Path(paths.common_scripts_dir(paths.find_skills_root()))
    target = scripts_dir / _EMITTER_ROOT
    violations: list[dict] = []
    seen: set[Path] = set()
    for entry in _LEGACY_FLAG_SCAN_ROOTS:
        scan_root = scripts_dir / entry
        if scan_root.is_dir():
            for p in _walk_py(scan_root):
                if p in seen:
                    continue
                seen.add(p)
                violations.extend(lint_file(p, root=scan_root))
        elif scan_root.is_file():
            if scan_root in seen:
                continue
            seen.add(scan_root)
            violations.extend(lint_file(scan_root, root=scan_root.parent))

    if args.baseline:
        output.success(
            {"violations": violations, "count": len(violations)},
            f"{len(violations)} dispatcher-hygiene violation(s)",
        )
        return

    if violations:
        output.error(
            f"{len(violations)} emitter(s) target prepare-pipeline.py --phase",
            hint="\n".join(
                f"{v['file']}:{v['line']} — {v['snippet']} — {v['fix']}"
                for v in violations
            ),
            next_action_command=(
                ".spec-workflow/sdd internal_lints/emitter_dispatcher_hygiene.py --baseline"
            ),
        )
        return
    output.success(
        {"checked": str(target)},
        "All recovery-command emitters route via pipeline-tick.py",
    )


if __name__ == "__main__":
    cli.run_main(main)
