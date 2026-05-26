#!/usr/bin/env python3
"""Surface runtime-version drift between declarative sources and tech.md.

Reads the declarative runtime-floor sources in the repo
(``package.json.engines``, ``pyproject.toml``, Python CI matrix,
``.python-version``) and compares them against the ``Node.js >= X`` /
``Python 3.Y+`` strings a steering tech.md declares. Mismatches are
emitted as a structured envelope so the factual-sync triage checklist
can fix drifts before a StrReplace pass.

This script never proposes edits. It emits a machine-readable
``drift`` list; the caller (agent) reconciles.

Usage::

    .spec-workflow/sdd util/scan-runtime-versions.py --workspace .
    .spec-workflow/sdd util/scan-runtime-versions.py \
        --workspace . --tech-path .spec-workflow/steering/tech.md
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
import os
import re
from pathlib import Path
from typing import Optional

from sdd_core import cli, output, paths


__sdd_manifest__ = {
    "summary": (
        "Report runtime-version drift between package.json / "
        "pyproject.toml / CI matrix and tech.md"
    ),
    "verbs": [
        "--workspace <path>",
        "--workspace <path> --tech-path <path-to-tech.md>",
    ],
    "flags": ["--workspace", "--tech-path"],
    "when": (
        "Run during factual-sync triage before StrReplace-ing runtime "
        "version strings in tech.md."
    ),
}


_VERSION_TOKEN_RE = re.compile(r"\d+(?:\.\d+){0,2}")


def _read_json(path: Path) -> Optional[dict]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _strip_leading_range(raw: str) -> str:
    """Collapse npm-style ``">=20"`` / ``"^20.1"`` into a bare version
    token so diff comparisons are apples-to-apples."""
    match = _VERSION_TOKEN_RE.search(raw or "")
    return match.group(0) if match else ""


def _first(seq):
    return next(iter(seq), None)


def _read_package_json_engines(project_root: Path) -> dict[str, str]:
    """Return ``engines`` mapping from package.json, or empty dict."""
    data = _read_json(project_root / "package.json") or {}
    engines = data.get("engines") or {}
    return {
        str(k): _strip_leading_range(str(v))
        for k, v in engines.items()
        if v
    }


def _read_pyproject_python_floor(project_root: Path) -> Optional[str]:
    """Extract the lower bound of ``requires-python`` from pyproject.toml.

    Best-effort regex — pyproject dependency parsing is over-engineered
    for this use case (the field is almost always a single ``">=3.Y"``).
    """
    path = project_root / "pyproject.toml"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(
        r'requires-python\s*=\s*"([^"]+)"', text,
    )
    if not match:
        return None
    raw = match.group(1).strip()
    # Most projects ship ``>=3.10`` / ``>=3.10,<4`` — take the lower.
    lower = raw.split(",")[0]
    return _strip_leading_range(lower) or None


def _read_python_version_file(project_root: Path) -> Optional[str]:
    path = project_root / ".python-version"
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return _strip_leading_range(raw) or None


def _read_ci_python_matrix(project_root: Path) -> list[str]:
    """Return Python versions referenced in .github/workflows/*.yml.

    Best-effort grep: a proper YAML parse is unnecessary — we only need
    the minimum version string for diff purposes.
    """
    wf_dir = project_root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    seen: set[str] = set()
    for entry in wf_dir.iterdir():
        if entry.suffix.lower() not in (".yml", ".yaml"):
            continue
        try:
            text = entry.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in re.finditer(r'python-version\s*:\s*["\']?([\d.]+)', text):
            seen.add(m.group(1))
        for m in re.finditer(
            r'["\']?(\d+\.\d+(?:\.\d+)?)["\']?', text,
        ):
            if re.search(r"python", text[max(0, m.start() - 60):m.start()], re.I):
                seen.add(m.group(1))
    return sorted(seen)


def _read_tech_md_claims(tech_path: Path) -> dict[str, list[str]]:
    """Extract claimed versions from tech.md.

    Returns a dict with ``node`` and ``python`` keys, each mapping to a
    list of version strings the doc mentions (e.g. ``">=18"`` → ``"18"``).
    Empty lists when tech.md is missing — the caller treats "no claim"
    as "no drift".
    """
    claims: dict[str, list[str]] = {"node": [], "python": []}
    if not tech_path.is_file():
        return claims
    try:
        text = tech_path.read_text(encoding="utf-8")
    except OSError:
        return claims
    for m in re.finditer(
        r"Node(?:\.js)?\s*(?:>=|≥)?\s*(\d+(?:\.\d+){0,2})",
        text, re.IGNORECASE,
    ):
        claims["node"].append(m.group(1))
    for m in re.finditer(
        r"Python\s*(\d+\.\d+(?:\.\d+)?)\+?", text, re.IGNORECASE,
    ):
        claims["python"].append(m.group(1))
    return claims


def _version_tuple(raw: str) -> tuple[int, ...]:
    """Parse a dotted version string into an int tuple.

    ``"3.14"`` → ``(3, 14)``; ``"3.14.4"`` → ``(3, 14, 4)``. Returns
    ``()`` on bad input so callers fall back to literal string
    comparison rather than silently accepting garbage.
    """
    try:
        return tuple(int(p) for p in raw.split(".") if p)
    except ValueError:
        return ()


def _satisfies_minimum(expected_min: str, claimed: str) -> bool:
    """Return True when ``claimed`` satisfies ``>=expected_min``."""
    exp_t = _version_tuple(expected_min)
    claim_t = _version_tuple(claimed)
    if not exp_t or not claim_t:
        return expected_min == claimed
    pad = max(len(exp_t), len(claim_t))
    exp_t = exp_t + (0,) * (pad - len(exp_t))
    claim_t = claim_t + (0,) * (pad - len(claim_t))
    return claim_t >= exp_t


def _compare(
    expected: Optional[str], claimed: list[str], label: str,
) -> Optional[dict]:
    """Return a drift entry when every ``claimed`` version fails to
    satisfy the ``>=expected`` minimum declared by the runtime config.
    Missing expected → no drift reportable (we can't contradict what we
    don't know)."""
    if not expected or not claimed:
        return None
    expected_bare = _strip_leading_range(expected)
    claimed_bare = [
        _strip_leading_range(c) for c in claimed if _strip_leading_range(c)
    ]
    if not claimed_bare:
        return None
    if any(_satisfies_minimum(expected_bare, c) for c in claimed_bare):
        return None
    return {
        "runtime": label,
        "expected_min": expected_bare,
        "tech_md_mentions": sorted(set(claimed_bare)),
    }


def _build_report(project_root: Path, tech_path: Path) -> dict:
    engines = _read_package_json_engines(project_root)
    py_pyproject = _read_pyproject_python_floor(project_root)
    py_file = _read_python_version_file(project_root)
    py_ci = _read_ci_python_matrix(project_root)

    # Authoritative Python floor: prefer pyproject, fall back to
    # ``.python-version``, then to the lowest CI matrix entry.
    py_floor = py_pyproject or py_file or _first(py_ci)

    tech_claims = _read_tech_md_claims(tech_path)

    drift: list[dict] = []
    node_drift = _compare(engines.get("node"), tech_claims["node"], "node")
    if node_drift:
        drift.append(node_drift)
    python_drift = _compare(py_floor, tech_claims["python"], "python")
    if python_drift:
        drift.append(python_drift)

    return {
        "project_root": str(project_root),
        "tech_path": str(tech_path),
        "sources": {
            "package_json_engines": engines,
            "pyproject_requires_python": py_pyproject,
            "python_version_file": py_file,
            "ci_python_matrix": py_ci,
        },
        "tech_md_claims": tech_claims,
        "drift": drift,
    }


def main() -> None:
    parser = cli.strict_parser(
        "Report runtime-version drift between declarative sources and tech.md",
    )
    parser.add_argument(
        "--tech-path",
        help=(
            "Path to tech.md (default: "
            ".spec-workflow/steering/tech.md relative to --workspace)."
        ),
    )
    args = parser.parse_args()

    project_root = Path(paths.resolve_project_path(args))
    tech_path = Path(
        args.tech_path or (project_root / ".spec-workflow" / "steering" / "tech.md"),
    )
    if not tech_path.is_absolute():
        tech_path = project_root / tech_path

    report = _build_report(project_root, tech_path)
    drift_count = len(report["drift"])
    summary = (
        "No runtime-version drift detected."
        if drift_count == 0
        else f"Runtime-version drift detected: {drift_count} entrie(s)."
    )
    output.success(report, summary)


if __name__ == "__main__":
    cli.run_main(main)
