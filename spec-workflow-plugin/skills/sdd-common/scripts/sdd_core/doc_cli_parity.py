"""Loader + checker for ``data/doc_cli_flag_parity.yaml``.

Single source of truth for "every flag a reference doc cites for a
shim invocation must exist on that shim's argparse, and every flag the
script no longer accepts must not appear in the doc". Adding a new
parity rule is a YAML edit only; this module owns the schema-thin
Python layer plus the introspection that resolves a script's argparse
flags from its module.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path

from .deps import require_pyyaml

__all__ = [
    "DATA_FILE",
    "FINDING_KIND_MISSING_REQUIRED_FLAG",
    "FINDING_KIND_FORBIDDEN_FLAG_IN_DOC",
    "ParityRule",
    "Finding",
    "load_rules",
    "script_flags",
    "doc_flags",
    "check_rule",
    "run_all",
]


DATA_FILE = Path(__file__).resolve().parent / "data" / "doc_cli_flag_parity.yaml"


# Finding-kind constants reused by the lint shim emitter and tests.
FINDING_KIND_MISSING_REQUIRED_FLAG = "missing_required_flag"
FINDING_KIND_FORBIDDEN_FLAG_IN_DOC = "forbidden_flag_in_doc"


@dataclass(frozen=True)
class ParityRule:
    reference: str
    script: str
    required_flags: tuple[str, ...]
    forbidden_flags: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class Finding:
    rule: ParityRule
    kind: str
    flag: str
    detail: str


def load_rules(path: Path | None = None) -> tuple[ParityRule, ...]:
    """Return the parity rules declared in the YAML file."""
    yaml = require_pyyaml()
    target = path or DATA_FILE
    raw = yaml.safe_load(target.read_text()) or {}
    out: list[ParityRule] = []
    for entry in (raw.get("parity") or []):
        out.append(
            ParityRule(
                reference=str(entry.get("reference", "")),
                script=str(entry.get("script", "")),
                required_flags=tuple(entry.get("required_flags") or ()),
                forbidden_flags=tuple(entry.get("forbidden_flags") or ()),
                reason=str(entry.get("reason", "")),
            )
        )
    return tuple(out)


def _scripts_root() -> Path:
    """Return the root of the ``scripts/`` tree (parent of ``sdd_core``)."""
    return Path(__file__).resolve().parent.parent


def _references_root() -> Path:
    """Return the ``references/`` directory of the sdd-common skill."""
    return _scripts_root().parent / "references"


def _load_script_module(script_rel: str):
    """Load the script as a module so its argparse parser can be introspected.

    ``script_rel`` is ``"<group>/<name>.py"`` (e.g. ``util/render-task-prompts.py``).
    Seeds a no-op ``_bootstrap`` module first so script-level
    ``import _bootstrap`` lines don't trigger the production bootstrap
    side-effects during introspection.
    """
    abs_path = _scripts_root() / script_rel
    if not abs_path.exists():
        raise FileNotFoundError(f"script not found: {abs_path}")
    sys.modules.setdefault("_bootstrap", types.ModuleType("_bootstrap"))
    if str(_scripts_root()) not in sys.path:
        sys.path.insert(0, str(_scripts_root()))
    mod_name = "_doc_cli_parity_" + re.sub(r"[^a-zA-Z0-9_]", "_", script_rel)
    spec = importlib.util.spec_from_file_location(mod_name, abs_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {abs_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _walk_actions(parser: argparse.ArgumentParser) -> list[str]:
    """Return every long flag (``--foo``) registered on ``parser`` and subparsers."""
    flags: list[str] = []
    for action in parser._actions:  # noqa: SLF001
        for opt in (action.option_strings or ()):
            if opt.startswith("--"):
                flags.append(opt)
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            for sub in action.choices.values():
                flags.extend(_walk_actions(sub))
    return flags


def script_flags(script_rel: str) -> set[str]:
    """Return the set of long flags exposed by ``script_rel``'s argparse.

    Tries module import first (when the script defines ``build_parser``
    or a top-level ``parser``); falls back to a literal scan of the
    source so scripts that bootstrap via ``import _bootstrap`` still
    surface their flags. Both paths cover the same flag vocabulary
    because ``add_argument("--foo", ...)`` is the canonical shape.
    """
    parser: argparse.ArgumentParser | None = None
    try:
        module = _load_script_module(script_rel)
    except Exception:
        module = None
    if module is not None:
        if hasattr(module, "build_parser"):
            parser = module.build_parser()
        elif hasattr(module, "parser"):
            parser = module.parser
        elif hasattr(module, "_build_parser"):
            parser = module._build_parser()  # noqa: SLF001
    if parser is None:
        return _grep_long_flags(_scripts_root() / script_rel)
    return set(_walk_actions(parser))


def _grep_long_flags(path: Path) -> set[str]:
    """Lightweight fallback: scan source for any ``--flag-name`` token.

    Scripts that delegate flag registration to a helper (e.g.
    ``cli.target_argument``) won't expose ``add_argument("--foo")`` at
    the call site, but their docstring / manifest / examples invariably
    mention the flag literal — so a generic scan still recovers the
    canonical surface.
    """
    text = path.read_text(errors="replace")
    return set(re.findall(r"--[a-zA-Z][a-zA-Z0-9-]+", text))


def doc_flags(reference_rel: str, *, script_filter: str = "") -> set[str]:
    """Return long flags cited inside the reference doc.

    With ``script_filter`` set, only flags appearing on lines that also
    mention the script path are returned — so ``--spec-name`` cited in
    an example for ``resolve-template.py`` does not contaminate the
    parity check for ``render-task-prompts.py``.
    """
    abs_path = _references_root() / Path(reference_rel).name
    if not abs_path.exists():
        abs_path = _references_root().parent / reference_rel
    text = abs_path.read_text(errors="replace")
    if not script_filter:
        return set(re.findall(r"--[a-zA-Z][a-zA-Z0-9-]+", text))
    found: set[str] = set()
    # Window over consecutive lines so a multi-line code block that
    # invokes the script captures any flags rendered below the head.
    lines = text.splitlines()
    in_script_block = False
    for line in lines:
        if script_filter in line:
            in_script_block = True
        if in_script_block:
            found.update(re.findall(r"--[a-zA-Z][a-zA-Z0-9-]+", line))
            # Reset the window at a blank or fence boundary.
            if not line.strip() or line.strip().startswith("```"):
                in_script_block = False
    return found


def check_rule(rule: ParityRule) -> list[Finding]:
    """Return findings for a single rule (empty list = pass)."""
    findings: list[Finding] = []
    parser_flags = script_flags(rule.script)
    cited = doc_flags(rule.reference, script_filter=rule.script)
    for flag in rule.required_flags:
        if flag not in parser_flags:
            findings.append(
                Finding(
                    rule=rule,
                    kind=FINDING_KIND_MISSING_REQUIRED_FLAG,
                    flag=flag,
                    detail=(
                        f"{rule.script} does not expose {flag} on its argparse"
                    ),
                )
            )
    for flag in rule.forbidden_flags:
        if flag in cited:
            findings.append(
                Finding(
                    rule=rule,
                    kind=FINDING_KIND_FORBIDDEN_FLAG_IN_DOC,
                    flag=flag,
                    detail=(
                        f"{rule.reference} cites {flag} but {rule.script} "
                        "no longer accepts it"
                    ),
                )
            )
    return findings


def run_all(path: Path | None = None) -> list[Finding]:
    """Return findings for every rule in the YAML allowlist."""
    out: list[Finding] = []
    for rule in load_rules(path):
        out.extend(check_rule(rule))
    return out
