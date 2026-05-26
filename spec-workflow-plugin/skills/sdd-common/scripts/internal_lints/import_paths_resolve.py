#!/usr/bin/env python3
"""Lint for dotted Python module paths in steering/spec prose.

Steering docs (``product.md``, ``tech.md``) routinely quote
``uvicorn <module>:app`` or ``python -m <module>`` invocations. When
the documented module diverges from the real source tree — e.g.
``uvicorn app.main:app`` vs ``uvicorn pti_service.main:app`` — the
drift goes unnoticed because no existing lint resolves dotted paths
against ``pyproject.toml`` / ``src/*`` package names.

Usage:
  import_paths_resolve.py            — scan and diff against baseline.
  import_paths_resolve.py --refresh  — rewrite the baseline.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path
from typing import Iterable

from internal_lints import LintFinding
from internal_lints import base as _base
from internal_lints.base import LintSpec
from internal_lints.baseline import (
    MANIFEST_PATH,
    diff_baseline,
    key_for,
    write_baseline,
)
from sdd_core import cli, output

try:
    from sdd_core.paths import iter_python_packages
except Exception:  # pragma: no cover — bootstrap fallback for tests
    iter_python_packages = None  # type: ignore[assignment]

from internal_lints._dispatch import rule_id_for

__all__ = [
    "LintFinding",
    "RULE_ID",
    "RULE_ID_UNRESOLVED",
    "SPEC",
    "scan_file",
    "analyze",
    "compare_baseline",
    "collect_finding_keys",
    "BASELINE_PATH",
]


RULE_ID = rule_id_for(__name__, __file__)
RULE_ID_UNRESOLVED = "import-path-unresolved"

# ``uvicorn pti_service.main:app`` or ``python -m pti_service.scheduler``.
# The dotted module is captured as group 1.
_IMPORT_RE = re.compile(
    r"\b(?:uvicorn|python\s+-m)\s+([A-Za-z_][\w.]*)",
)

_DEFAULT_DOC_DIRS: tuple[str, ...] = (
    ".spec-workflow/steering",
    ".spec-workflow/specs",
)


def _first_segment(dotted: str) -> str:
    return dotted.split(".", 1)[0]


def _find_project_root(path: Path) -> Path:
    """Walk up until a ``pyproject.toml`` / ``src`` / ``.git`` marker is found."""
    cur = path.resolve().parent
    while cur != cur.parent:
        if (
            (cur / "pyproject.toml").is_file()
            or (cur / "src").is_dir()
            or (cur / ".git").is_dir()
        ):
            return cur
        cur = cur.parent
    return path.resolve().parent


def _packages_for(root: Path) -> list[str]:
    if iter_python_packages is None:
        return []
    try:
        return iter_python_packages(root)
    except Exception:  # pragma: no cover — defensive
        return []


def scan_file(
    path: Path, *, project_root: "Path | None" = None,
) -> list[LintFinding]:
    """Return findings for dotted module paths in *path*.

    Markdown files with no matches contribute zero findings. When no
    packages are discoverable at all (brand-new project, stripped
    checkout), the lint is a no-op rather than noisy.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    root = project_root or _find_project_root(path)
    packages = _packages_for(root)
    if not packages:
        return []

    package_set = set(packages)
    findings: list[LintFinding] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for match in _IMPORT_RE.finditer(line):
            dotted = match.group(1)
            segment = _first_segment(dotted)
            if segment in package_set:
                continue
            findings.append(
                LintFinding(
                    rule_id=RULE_ID_UNRESOLVED,
                    severity="warning",
                    file=str(path),
                    line=lineno,
                    message=(
                        f"dotted module '{dotted}' does not resolve against "
                        f"available packages {sorted(package_set)}"
                    ),
                    extra={
                        "dotted_path": dotted,
                        "segment": segment,
                        "fix_hint": (
                            f"Rename '{segment}' to one of {sorted(package_set)}"
                        ),
                        "available_packages": sorted(package_set),
                    },
                )
            )
    return findings


SPEC = LintSpec(
    rule_id=RULE_ID,
    roots=_DEFAULT_DOC_DIRS,
    file_glob="*.md",
    exclude_parts=("__pycache__", "archive", ".archive"),
)


def analyze(repo_root: "Path | str | None" = None) -> list[LintFinding]:
    """Run the lint across the steering/spec docs under *repo_root*.

    Defaults to the cwd when *repo_root* is omitted. Package discovery
    rebases to *repo_root* so a single workflow's package set drives
    every doc finding.
    """
    if repo_root is None:
        repo_root = Path.cwd()
    repo = Path(repo_root)
    targets: list[Path] = []
    for sub in _DEFAULT_DOC_DIRS:
        root = repo / sub
        if not root.exists():
            continue
        targets.extend(_base.iter_files(
            [root], SPEC.exclude_parts, suffix=".md",
        ))
    findings: list[LintFinding] = []
    for path in targets:
        findings.extend(scan_file(path, project_root=repo))
    return findings


def collect_finding_keys(findings: Iterable[LintFinding]) -> list[str]:
    return sorted({
        key_for(f) for f in findings if f.rule_id == RULE_ID_UNRESOLVED
    })


def compare_baseline(
    findings: Iterable[LintFinding],
    *,
    manifest_path: "Path | str | None" = None,
) -> dict[str, list[str]]:
    target = Path(manifest_path) if manifest_path is not None else None
    observed = collect_finding_keys(list(findings))
    return diff_baseline(observed, rule_id=RULE_ID, manifest_path=target)


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "--refresh", action="store_true",
        help="Rewrite the baseline to match observed findings.",
    )
    args = parser.parse_args()

    project_path = getattr(args, "project_path", None)
    repo_root = Path(project_path) if project_path else Path.cwd()
    findings = analyze(repo_root)

    if args.refresh:
        observed = collect_finding_keys(findings)
        write_baseline(RULE_ID, observed)
        output.success(
            {"rule_id": RULE_ID, "count": len(observed)},
            f"{RULE_ID}: baseline refreshed",
        )
        return

    diff = compare_baseline(findings)
    ok = not diff["new"] and not diff["stale"]
    payload = {
        "ok": ok,
        "new_findings": diff["new"],
        "stale_entries": diff["stale"],
        "known": diff["known"],
        "findings": [f.to_payload() for f in findings],
    }
    message = (
        f"{RULE_ID}: {len(diff['new'])} new, "
        f"{len(diff['stale'])} stale, {len(diff['known'])} known"
    )
    if ok:
        output.result(payload, message, exit_code=0)
        return
    from sdd_core.command_templates import build_baseline_refresh_command
    output.error(
        message,
        hint=(
            "Dotted module paths in steering/spec docs must resolve "
            "against the project's package list."
        ),
        next_action_command=build_baseline_refresh_command(RULE_ID),
    )


BASELINE_PATH = MANIFEST_PATH


if __name__ == "__main__":
    cli.run_main(main)
