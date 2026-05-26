"""Shared scaffolding for AST-based lints.

A concrete lint declares a ``NodeChecker`` (what to flag per AST node)
and a ``LintSpec`` (rule id, roots, baseline path, checkers). ``run_lint``
walks the tree, parses each ``*.py``, invokes every checker, diffs
against the baseline, and emits the canonical success / error envelope
through :mod:`sdd_core.output`.
"""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol, Sequence, runtime_checkable

from sdd_core import output
from sdd_core.paths import find_workflow_root

from . import LintFinding
from .baseline import diff_baseline, key_for, read_baseline, write_baseline

__all__ = [
    "NodeChecker",
    "TextChecker",
    "PathChecker",
    "LintSpec",
    "run_lint",
    "run_lint_cli",
    "run_text_lint",
    "scan_file",
    "scan_text_file",
    "scan_path",
    "iter_py_files",
    "iter_files",
    "analyze_with_spec",
    "compare_baseline_with_spec",
]


@runtime_checkable
class NodeChecker(Protocol):
    """Strategy — inspect one AST node, yield zero or more findings."""

    rule_id: str
    severity: str

    def check(self, node: ast.AST, path: Path) -> Iterable[LintFinding]: ...


@runtime_checkable
class TextChecker(Protocol):
    """Strategy — inspect one line of a text file, yield zero or more findings."""

    rule_id: str
    severity: str

    def check_line(
        self, line: str, lineno: int, path: Path,
    ) -> Iterable[LintFinding]: ...


@runtime_checkable
class PathChecker(Protocol):
    """Strategy — inspect a file path (no I/O), yield zero or more findings.

    File-level checks (filename pattern, parent directory, etc.) declare
    a ``PathChecker`` so the runner walks the path inventory once
    instead of re-parsing each file's AST.
    """

    rule_id: str
    severity: str

    def check_path(self, path: Path) -> Iterable[LintFinding]: ...


@dataclass(frozen=True)
class LintSpec:
    """Declarative lint definition — checkers + roots + rule id."""

    rule_id: str
    roots: tuple[str, ...]
    checkers: tuple[NodeChecker, ...] = ()
    text_checkers: tuple[TextChecker, ...] = ()
    path_checkers: tuple[PathChecker, ...] = ()
    file_glob: str = "*.py"
    exclude_parts: tuple[str, ...] = field(
        default_factory=lambda: ("__pycache__",),
    )
    refresh_command: "str | None" = None
    manifest_path: "Path | None" = None

    def analyze(
        self, repo_root: "Path | str | None" = None,
    ) -> list[LintFinding]:
        """Walk this spec's roots and return raw findings (no envelope)."""
        return analyze_with_spec(self, Path(repo_root) if repo_root else None)

    def compare_baseline(
        self,
        findings: Iterable[LintFinding],
        *,
        manifest_path: "Path | str | None" = None,
    ) -> dict[str, list[str]]:
        """Diff observed findings against this spec's committed baseline."""
        return compare_baseline_with_spec(
            self, findings, manifest_path=manifest_path,
        )


def iter_py_files(roots: Sequence[Path], exclude: Sequence[str]) -> list[Path]:
    """Yield ``*.py`` files under *roots*, skipping *exclude* directory names."""
    return iter_files(roots, exclude, suffix=".py")


def iter_files(
    roots: Sequence[Path],
    exclude: Sequence[str],
    *,
    suffix: str = ".py",
    name: "str | None" = None,
) -> list[Path]:
    """Yield files under *roots*, filtered by ``suffix`` or exact ``name``."""
    out: list[Path] = []
    excluded = set(exclude)
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, files in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in excluded]
            for fname in files:
                if name is not None:
                    if fname == name:
                        out.append(Path(dirpath) / fname)
                elif fname.endswith(suffix):
                    out.append(Path(dirpath) / fname)
    return sorted(out)


def scan_file(path: Path, checkers: Sequence[NodeChecker]) -> list[LintFinding]:
    """Parse *path* and run every checker against every AST node."""
    if not checkers:
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return []
    findings: list[LintFinding] = []
    for node in ast.walk(tree):
        for checker in checkers:
            findings.extend(checker.check(node, path))
    return findings


def scan_path(
    path: Path, checkers: Sequence[PathChecker],
) -> list[LintFinding]:
    """Run path-mode checkers against *path* (no file I/O)."""
    if not checkers:
        return []
    findings: list[LintFinding] = []
    for checker in checkers:
        findings.extend(checker.check_path(path))
    return findings


def scan_text_file(
    path: Path, checkers: Sequence[TextChecker],
) -> list[LintFinding]:
    """Run text-mode line scanners across *path*.

    Checkers may declare an optional ``prepare(path, text)`` method;
    when present it is invoked once per file before the per-line loop
    so file-level state (e.g. "does this file mention the ceremony
    reference at all?") can be computed once and reused per line.
    """
    if not checkers:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for checker in checkers:
        prepare = getattr(checker, "prepare", None)
        if prepare is not None:
            prepare(path, text)
    findings: list[LintFinding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for checker in checkers:
            findings.extend(checker.check_line(line, lineno, path))
    return findings


def _resolve_repo() -> Path:
    try:
        return find_workflow_root()
    except FileNotFoundError:
        return Path.cwd()


def _emit_envelope(
    spec: LintSpec, findings: list[LintFinding], *, refresh: bool,
) -> None:
    observed = sorted({key_for(f) for f in findings})
    if refresh:
        write_baseline(
            spec.rule_id, observed, manifest_path=spec.manifest_path,
        )
        output.success(
            {"rule_id": spec.rule_id, "count": len(observed)},
            f"{spec.rule_id}: baseline refreshed",
        )
        return
    diff = diff_baseline(
        observed, rule_id=spec.rule_id, manifest_path=spec.manifest_path,
    )
    if diff["new"] or diff["stale"]:
        next_cmd = spec.refresh_command or _default_refresh_command(spec)
        output.error(
            f"{spec.rule_id}: new={len(diff['new'])} stale={len(diff['stale'])}",
            hint="Fix the new findings or refresh the baseline.",
            next_action_command=next_cmd,
        )
    output.success({"known": diff["known"]}, f"{spec.rule_id}: clean")


def _default_refresh_command(spec: LintSpec) -> str:
    """Executable-shim form — single source via ``command_templates``."""
    try:
        from sdd_core.command_templates import build_baseline_refresh_command
        return build_baseline_refresh_command(spec.rule_id)
    except Exception:
        return (
            f".spec-workflow/sdd internal_lints/baseline-refresh.py "
            f"--rule {spec.rule_id}"
        )


def run_lint(spec: LintSpec, *, refresh: bool = False) -> None:
    """Walk *spec*'s roots, run every checker, emit success / error."""
    repo = _resolve_repo()
    roots = [repo / r for r in spec.roots]
    findings: list[LintFinding] = []
    if spec.checkers:
        for path in iter_py_files(roots, spec.exclude_parts):
            findings.extend(scan_file(path, spec.checkers))
    if spec.text_checkers:
        for path in _resolve_text_file_set(roots, spec):
            findings.extend(scan_text_file(path, spec.text_checkers))
    if spec.path_checkers:
        for path in _resolve_text_file_set(roots, spec):
            findings.extend(scan_path(path, spec.path_checkers))
    _emit_envelope(spec, findings, refresh=refresh)


def run_text_lint(spec: LintSpec, *, refresh: bool = False) -> None:
    """Convenience wrapper for text-only lints (e.g. SKILL.md scanners)."""
    repo = _resolve_repo()
    roots = [repo / r for r in spec.roots]
    findings: list[LintFinding] = []
    for path in _resolve_text_file_set(roots, spec):
        findings.extend(scan_text_file(path, spec.text_checkers))
    _emit_envelope(spec, findings, refresh=refresh)


def _resolve_text_file_set(roots: Sequence[Path], spec: LintSpec) -> list[Path]:
    """Resolve files matching ``spec.file_glob`` for text-mode scanning."""
    glob = spec.file_glob
    if glob.startswith("*.") and "/" not in glob:
        return iter_files(roots, spec.exclude_parts, suffix=glob[1:])
    # Exact filename match (e.g. ``SKILL.md``).
    return iter_files(roots, spec.exclude_parts, name=glob)


def analyze_with_spec(
    spec: LintSpec, repo_root: "Path | None" = None,
) -> list[LintFinding]:
    """Walk *spec*'s roots and return raw findings (no envelope emission).

    Used by the back-compat ``analyze()`` wrappers each lint module
    keeps for tests + the aggregator dispatch in
    ``review/check-template-compliance.py``.
    """
    if repo_root is None:
        repo_root = _resolve_repo()
    roots = [Path(repo_root) / r for r in spec.roots]
    findings: list[LintFinding] = []
    if spec.checkers:
        for path in iter_py_files(roots, spec.exclude_parts):
            findings.extend(scan_file(path, spec.checkers))
    if spec.text_checkers:
        for path in _resolve_text_file_set(roots, spec):
            findings.extend(scan_text_file(path, spec.text_checkers))
    if spec.path_checkers:
        for path in _resolve_text_file_set(roots, spec):
            findings.extend(scan_path(path, spec.path_checkers))
    return findings


def compare_baseline_with_spec(
    spec: LintSpec,
    findings: Iterable[LintFinding],
    *,
    manifest_path: "Path | str | None" = None,
) -> dict[str, list[str]]:
    """Diff observed findings against the spec's committed baseline."""
    target = Path(manifest_path) if manifest_path is not None else spec.manifest_path
    observed = sorted({key_for(f) for f in findings})
    return diff_baseline(observed, rule_id=spec.rule_id, manifest_path=target)


def run_lint_cli(spec: LintSpec) -> None:
    """Standard ``--refresh`` CLI shape for AST + text lints.

    Per-module ``main()`` collapses to ``run_lint_cli(SPEC)``. Lints
    needing extra flags (``error_envelopes`` strict mode, etc.) keep
    their bespoke entry point.
    """
    from sdd_core import cli

    parser = cli.strict_parser(spec.__doc__ or "")
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    args = parser.parse_args()
    runner = (
        run_text_lint
        if spec.text_checkers and not spec.checkers and not spec.path_checkers
        else run_lint
    )
    runner(spec, refresh=args.refresh)
