#!/usr/bin/env python3
"""Detect drift between dependency manifests and tech.md.

Usage: detect-dependency-drift.py <tech-md-file> <manifest-file>
Compares technologies mentioned in tech.md against a package manifest
(package.json, requirements.txt) and reports mismatches.

Exit codes: see `script-conventions.md` § Exit Codes (canonical policy).
Drift detection follows the policy:
  0 = no drift or skipped (envelope ``status`` distinguishes),
  1 = drift detected or user-facing error,
  2 = system error.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import os
import re

from sdd_core import output, cli
from skill_helpers import safe_open


def extract_tech_dependencies(tech_file: str) -> set[str]:
    """Extract technology/dependency names from backtick-quoted terms in tech.md."""
    deps = set()
    with safe_open(tech_file) as f:
        content = f.read()
    for match in re.finditer(r"`([a-zA-Z][\w.-]*)`", content):
        deps.add(match.group(1).lower())
    return deps


def _parse_package_json(path: str) -> set[str]:
    try:
        data = output.safe_read_json(path)
    except ValueError as e:
        output.error(f"Malformed JSON in {path}: {e}")
    if data is None:
        output.error(f"File not found: {path}")
    deps = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        if key in data:
            deps.update(k.lower() for k in data[key].keys())
    return deps


def _parse_requirements_txt(path: str) -> set[str]:
    deps = set()
    with safe_open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                name = re.split(r"[><=!~\[]", line)[0].strip().lower()
                if name:
                    deps.add(name)
    return deps


_TOML_DEP_SECTIONS = {
    "[project.dependencies]",
    "[project.optional-dependencies]",
    "[tool.poetry.dependencies]",
    "[tool.poetry.dev-dependencies]",
    "[dependencies]",
    "[dev-dependencies]",
}


def _parse_toml(path: str) -> set[str]:
    deps = set()
    in_dep_section = False
    with safe_open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("["):
                in_dep_section = stripped in _TOML_DEP_SECTIONS
                continue
            if not in_dep_section:
                continue
            match = re.match(r'^(\S+)\s*=', stripped)
            if match:
                deps.add(match.group(1).lower())
    return deps


_MANIFEST_PARSERS = {
    "package.json": _parse_package_json,
    "requirements.txt": _parse_requirements_txt,
}
_SUFFIX_PARSERS = {
    ".toml": _parse_toml,
}


def extract_manifest_dependencies(manifest_file: str) -> set[str] | None:
    """Extract dependency names from a package manifest. Returns None if format is unsupported."""
    basename = os.path.basename(manifest_file)
    _, ext = os.path.splitext(basename)
    parser = _MANIFEST_PARSERS.get(basename) or _SUFFIX_PARSERS.get(ext)
    if parser is None:
        return None
    return parser(manifest_file)


KNOWN_FRAMEWORKS = {
    "react", "vue", "angular", "express", "fastify", "django", "flask",
    "spring", "rails", "next", "nuxt", "svelte", "nest", "koa",
}


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("tech_file", help="Path to tech.md")
    parser.add_argument("manifest_file", help="Path to package manifest")
    args = parser.parse_args()

    tech_deps = extract_tech_dependencies(args.tech_file)
    manifest_deps = extract_manifest_dependencies(args.manifest_file)

    if manifest_deps is None:
        output.result(
            {"result": "skipped", "reason": f"Unsupported manifest: {os.path.basename(args.manifest_file)}"},
            "Skipped — unsupported manifest format",
            exit_code=0,
        )
        return  # defensive: output.result() exits, but guard against future refactor

    in_tech_not_manifest = sorted((tech_deps & KNOWN_FRAMEWORKS) - manifest_deps)

    if in_tech_not_manifest:
        output.error(
            f"Drift detected: {len(in_tech_not_manifest)} framework(s) in tech.md but not in manifest",
            hint=f"Missing from manifest: {', '.join(in_tech_not_manifest)}",
        )
    else:
        output.success(
            {"result": "no_drift"},
            "No significant drift detected",
        )


if __name__ == "__main__":
    cli.run_main(main)
