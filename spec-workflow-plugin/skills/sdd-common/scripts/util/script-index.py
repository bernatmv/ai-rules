#!/usr/bin/env python3
"""Index of agent-facing scripts under ``util/`` and ``review/``.

Walks the ``util/`` and ``review/`` packages of ``sdd-common/scripts``
and emits a JSON registry of each script's public verbs and flags so
agents can answer "which script?" and "which flag?" questions without
reverse-engineering ``--help`` for every tool.

The index is derived from each script source via lightweight AST
reflection (no ``importlib`` side effects, so it works even for
scripts that would otherwise require ``argparse`` parsing side
effects). For each ``parser.add_argument(...)`` call it captures every
declared flag name plus the first line of the docstring.

Usage:
  script-index.py                # full registry (all scripts)
  script-index.py --script util/generate-prompt.py   # one entry
  script-index.py --search prompt                    # fuzzy match
  script-index.py --flag --prompt-id                 # reverse lookup

Exit code: 0 always (result in JSON envelope).
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import ast
import difflib
import os
from pathlib import Path

from sdd_core import cli, output


__sdd_manifest__ = {
    "summary": "Index of agent-facing scripts under util/ and review/",
    "verbs": [
        "(no args)",
        "--script <path>",
        "--search <term>",
        "--flag <--flag-name>",
    ],
    "aliases": {},
    "flags": ["--script", "--search", "--flag"],
}


_HERE = Path(__file__).resolve().parent.parent
_INDEXED_DIRS = ("util", "review")

# difflib cutoffs (Ousterhout's "magic constants -> named with rationale"):
#
# - ``_SEARCH_FUZZY_PATH_CUTOFF = 0.3`` — permissive, because agents often
#   paraphrase a script name (``prompt-registry-get`` vs
#   ``generate-prompt``) and we'd rather surface a close neighbour than
#   nothing. The substring-match path fires first; this fuzzy tier is
#   a fallback.
# - ``_REVERSE_LOOKUP_FLAG_CUTOFF = 0.5`` — stricter, because flag names
#   are short and near-neighbours are often unrelated (``--doc`` vs
#   ``--type``). False positives on this tier waste agent round-trips.
# - ``_SCRIPT_NOT_FOUND_CUTOFF = 0.4`` — middle ground for the
#   "Script not found: X. Did you mean Y?" hint. Tuned empirically to
#   catch typos like "util/prompt-registry-get.py" →
#   "util/generate-prompt.py" without surfacing unrelated scripts.
_SEARCH_FUZZY_PATH_CUTOFF = 0.3
_REVERSE_LOOKUP_FLAG_CUTOFF = 0.5
_SCRIPT_NOT_FOUND_CUTOFF = 0.4


def _extract_docstring(tree: ast.Module) -> str:
    """Return the first sentence of the module-level docstring."""
    doc = ast.get_docstring(tree) or ""
    first = doc.strip().splitlines()[0] if doc.strip() else ""
    return first.rstrip(".")


def _extract_manifest(tree: ast.Module) -> dict | None:
    """Return the ``__sdd_manifest__`` dict literal if declared.

    Walks the module body looking for a top-level assignment of the
    form ``__sdd_manifest__ = {...}``. Uses :func:`ast.literal_eval` so
    the manifest stays statically analysable — no import side effects,
    no arbitrary code execution, and the manifest cannot secretly
    depend on runtime state.
    """
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = node.targets
        if len(targets) != 1:
            continue
        target = targets[0]
        if not isinstance(target, ast.Name) or target.id != "__sdd_manifest__":
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        try:
            return ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return None
    return None


def _flag_names_from_call(call: ast.Call) -> list[str]:
    """Extract ``--flag`` / ``-f`` positional strings from ``add_argument``."""
    flags: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            val = arg.value
            if val.startswith("-"):
                flags.append(val)
    return flags


def _iter_add_argument_calls(tree: ast.Module):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "add_argument":
            yield node


def _script_manifest(path: Path) -> dict:
    """Return the manifest entry for a single script file."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "path": str(path.relative_to(_HERE)),
            "error": str(exc),
        }
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "path": str(path.relative_to(_HERE)),
            "error": f"syntax error: {exc}",
        }

    flags: list[str] = []
    for call in _iter_add_argument_calls(tree):
        flags.extend(_flag_names_from_call(call))
    # Dedupe while preserving order.
    seen: set[str] = set()
    unique_flags = [f for f in flags if not (f in seen or seen.add(f))]

    # Prefer the explicit ``__sdd_manifest__`` dict when declared.
    # Manifest fields override AST-derived fields so scripts that vend
    # flags via helpers (e.g. ``cli.add_document_selectors``) or
    # sub-parsers still report their full surface. AST-derived flags
    # merge in at the end so a script that declares a manifest without
    # a ``flags`` key still gets argparse coverage.
    manifest = _extract_manifest(tree) or {}
    entry: dict = {
        "path": str(path.relative_to(_HERE)),
        "summary": manifest.get("summary") or _extract_docstring(tree),
        "flags": (
            list(manifest["flags"])
            if manifest.get("flags")
            else unique_flags
        ),
    }
    for key in ("verbs", "aliases", "produces_key_value_flags"):
        if key in manifest:
            entry[key] = manifest[key]
    if manifest:
        entry["manifest_source"] = "declared"
    else:
        entry["manifest_source"] = "ast"
    return entry


def _walk_scripts() -> list[dict]:
    """Return manifests for every indexable script under the target dirs."""
    out: list[dict] = []
    for sub in _INDEXED_DIRS:
        root = _HERE / sub
        if not root.is_dir():
            continue
        for entry in sorted(root.glob("*.py")):
            name = entry.name
            if name.startswith("_") or name == "__init__.py":
                continue
            out.append(_script_manifest(entry))
    return out


def _find_by_path(manifests: list[dict], rel: str) -> dict | None:
    rel = rel.replace(os.sep, "/")
    for m in manifests:
        if m["path"].replace(os.sep, "/") == rel:
            return m
    return None


def _search_by_term(manifests: list[dict], term: str) -> list[dict]:
    """Return manifests whose path or summary loosely contains ``term``."""
    term_l = term.lower()
    hits = []
    for m in manifests:
        hay = (m["path"] + " " + m.get("summary", "")).lower()
        if term_l in hay:
            hits.append(m)
    if hits:
        return hits
    # Fall back to fuzzy path match so "prompt-registry-get" still
    # surfaces ``util/generate-prompt.py``.
    paths = [m["path"] for m in manifests]
    close = difflib.get_close_matches(
        term, paths, n=5, cutoff=_SEARCH_FUZZY_PATH_CUTOFF,
    )
    return [m for m in manifests if m["path"] in close]


def _reverse_lookup_flag(manifests: list[dict], flag: str) -> list[dict]:
    """Return manifests that declare ``flag`` (or a close neighbour)."""
    hits = [m for m in manifests if flag in m.get("flags", [])]
    if hits:
        return hits
    flat_flags = {f for m in manifests for f in m.get("flags", [])}
    close = difflib.get_close_matches(
        flag, list(flat_flags), n=5, cutoff=_REVERSE_LOOKUP_FLAG_CUTOFF,
    )
    return [m for m in manifests if any(f in close for f in m.get("flags", []))]


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "--script", default=None,
        help="Return manifest for a single script (path relative to scripts/)",
    )
    parser.add_argument(
        "--search", default=None,
        help="Fuzzy-match scripts by path or summary substring",
    )
    parser.add_argument(
        "--flag", default=None,
        help="Reverse-lookup scripts that declare a given --flag",
    )
    args = parser.parse_args()

    manifests = _walk_scripts()

    # Each branch terminates the script via ``output.success`` /
    # ``output.error`` (which raise ``SystemExit``); the explicit
    # ``return`` statements keep that terminator contract visible.
    if args.script:
        entry = _find_by_path(manifests, args.script)
        if not entry:
            close = difflib.get_close_matches(
                args.script,
                [m["path"] for m in manifests],
                n=5, cutoff=_SCRIPT_NOT_FOUND_CUTOFF,
            )
            output.error(
                f"Script not found: {args.script}",
                hint=(
                    f"Did you mean: {', '.join(close)}?"
                    if close else
                    "Run without --script to list all indexed scripts."
                ),
            )
            return
        output.success({"script": entry}, f"Indexed {entry['path']}")
        return

    if args.search:
        matches = _search_by_term(manifests, args.search)
        output.success(
            {"matches": matches, "query": args.search},
            f"{len(matches)} script(s) matched '{args.search}'",
        )
        return

    if args.flag:
        matches = _reverse_lookup_flag(manifests, args.flag)
        output.success(
            {"matches": matches, "flag": args.flag},
            f"{len(matches)} script(s) declare '{args.flag}'",
        )
        return

    output.success(
        {"scripts": manifests, "indexed_dirs": list(_INDEXED_DIRS)},
        f"{len(manifests)} script(s) indexed",
    )


if __name__ == "__main__":
    cli.run_main(main)
