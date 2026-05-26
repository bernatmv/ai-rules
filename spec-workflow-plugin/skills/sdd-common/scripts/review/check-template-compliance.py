#!/usr/bin/env python3
"""Check document compliance against a template by comparing section headings.

Usage:
    check-template-compliance.py <template-file> <document-file>
    check-template-compliance.py --spec-name NAME [--doc requirements.md] \\
        [--template PATH]

Exit code: 0 always for a valid run. Compliance rating travels in
``data.rating`` (``COMPLIANT`` / ``PARTIAL`` / ``NON_COMPLIANT``);
non-COMPLIANT outcomes set ``data.outcome="partial"`` so callers can
branch on the structured envelope instead of the exit code.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import importlib
import json
import os
import re
from pathlib import Path
from typing import Callable

from sdd_core import output, cli, paths
from sdd_core.compliance import ComplianceRating
from sdd_core.matchers import WordMatcher
from sdd_core.paths import doc_dir_path, templates_dir
from sdd_core.skill_md_rules import load_rules, skill_name_from_md_path
from skill_helpers import iter_effective_lines


# Single-row additions unlock new SKILL.md lints — OCP over a copy-
# paste block per rule. Each row: (module, kind, literal-fn,
# signature-adapter). ``sig`` receives the module and returns the
# per-file callable invoked with ``(path, rules)``.
def _prompt_refs_adapter(mod):
    ids = mod.registry_prompt_ids()
    return lambda path, rules: mod.lint_file(path, rules, ids)


LINT_REGISTRY: tuple[tuple[str, str, Callable[[dict], str], Callable], ...] = (
    (
        "internal_lints.skill_md_prompt_refs",
        "prompt_invocation_adjacency",
        lambda v: v.get("prompt_id") or "prompt-invocation",
        _prompt_refs_adapter,
    ),
    (
        "internal_lints.skill_md_abs_paths",
        "absolute_skill_paths",
        lambda v: "absolute_skill_path",
        lambda mod: mod.lint_file,
    ),
    (
        "internal_lints.skill_md_toc",
        "toc_completeness",
        lambda v: v.get("kind") or "toc_completeness",
        lambda mod: mod.lint_file,
    ),
    (
        "internal_lints.skill_md_hand_rendered_options",
        "hand_rendered_options",
        lambda v: v.get("kind") or "hand_rendered_options",
        lambda mod: mod.lint_file,
    ),
    (
        "internal_lints.skill_md_pair_key_literals",
        "pair_key_literals",
        lambda v: v.get("kind") or "pair_key_literal",
        lambda mod: mod.lint_file,
    ),
    (
        "internal_lints.skill_md_assessment_staging_literals",
        "assessment_staging_literals",
        lambda v: v.get("kind") or "assessment_staging_literal",
        lambda mod: mod.lint_file,
    ),
    (
        "internal_lints.skill_md_dependency_order",
        "dependency_table_read_before_run",
        lambda v: v.get("kind") or "dependency_read_after_run",
        lambda mod: mod.lint_file,
    ),
    (
        "internal_lints.skill_md_batch_hygiene",
        "batch_hygiene",
        lambda v: v.get("kind") or "batch_hygiene",
        lambda mod: mod.lint_file,
    ),
)


def _run_skill_md_lints(md_path: str, rules: dict) -> list[dict]:
    """Invoke every registered SKILL.md lint against *md_path*.

    Adding a rule is one :data:`LINT_REGISTRY` row — no edits to this
    function.
    """
    findings: list[dict] = []
    path = Path(md_path)
    for mod_name, kind, literal_of, sig_adapter in LINT_REGISTRY:
        mod = importlib.import_module(mod_name)
        lint_fn = sig_adapter(mod)
        for v in lint_fn(path, rules):
            entry: dict = {
                "literal": literal_of(v),
                "remediation": v.get("message", ""),
                "file": v.get("file", md_path),
                "line": v.get("line"),
                "kind": kind,
            }
            if v.get("snippet"):
                entry["snippet"] = v.get("snippet")
            findings.append(entry)
    return findings

_PAREN_SUFFIX_PHRASES = WordMatcher(
    ("if applicable", "optional", "recommended", "required"),
)
_PAREN_SUFFIX_RE = _PAREN_SUFFIX_PHRASES.compose(
    prefix=r"\s*\(",
    suffix=r"\)\s*$",
)

FREEDOM_HEADER_RE = re.compile(r"\|\s*Freedom\s*\|", re.IGNORECASE)


def check_skill_md_literals(md_path: str) -> list[dict]:
    """Return one finding per rule violation present in ``md_path``.

    Returns an empty list when the file passes. Safe to call on missing
    files (returns ``[]``) so tests can exercise the happy path without
    extra fixtures. Per-skill positive rules (required literals, budget,
    freedom-column) are loaded from
    ``sdd_core/data/skill_md_rules.yaml`` keyed by the parent directory
    name (e.g. ``sdd-create-spec``).
    """
    try:
        with open(md_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return []
    bundle = load_rules()
    findings: list[dict] = []
    for entry in bundle.forbidden:
        if entry.literal in content:
            findings.append({
                "literal": entry.literal,
                "remediation": entry.remediation,
                "file": md_path,
                "kind": "forbidden",
            })

    skill_name = skill_name_from_md_path(md_path)
    if skill_name and skill_name in bundle.per_skill:
        rules = bundle.per_skill[skill_name]
        for entry in rules.required_literals:
            if entry.literal not in content:
                findings.append({
                    "literal": entry.literal,
                    "remediation": entry.remediation,
                    "file": md_path,
                    "kind": "missing_required",
                })
        if rules.max_lines:
            line_count = content.count("\n") + (0 if content.endswith("\n") else 1)
            if line_count > rules.max_lines:
                findings.append({
                    "literal": f"line-budget:{rules.max_lines}",
                    "remediation": (
                        f"SKILL.md is {line_count} lines (budget "
                        f"{rules.max_lines}). Trim prose Claude already "
                        "knows (best-practices § *Concise is key*)."
                    ),
                    "file": md_path,
                    "kind": "budget",
                    "line_count": line_count,
                    "max_lines": rules.max_lines,
                })
        if rules.require_freedom_column and not FREEDOM_HEADER_RE.search(content):
            findings.append({
                "literal": "| Freedom |",
                "remediation": (
                    "Dependencies table must include a Freedom (L/M/H) column "
                    "per best-practices § *Set appropriate degrees of freedom*."
                ),
                "file": md_path,
                "kind": "missing_required",
            })
    return findings


def _normalize_heading(heading: str) -> str:
    """Strip trailing parenthetical qualifiers so template and doc headings match."""
    return _PAREN_SUFFIX_RE.sub("", heading).strip()


def _extract_headings(filepath: str, level: int = 2) -> list[str]:
    """Extract markdown headings at the given level, skipping frontmatter and code blocks."""
    prefix = "#" * level + " "
    headings = []
    for line in iter_effective_lines(filepath):
        if line.startswith(prefix):
            headings.append(line[len(prefix):].strip())
    return headings


def _resolve_paths(args, project_path: str) -> tuple[str, str]:
    """Resolve (template_file, document_file) from positional or flag inputs.

    Precedence: positional pair > ``--spec-name`` + ``--doc`` (+
    optional ``--template``). The positional form keeps working
    unchanged; the flag form accepts agents' reflexive ``--spec-name``
    invocations.
    """
    tpl_positional = getattr(args, "template_file", None)
    doc_positional = getattr(args, "document_file", None)
    if tpl_positional and doc_positional:
        return tpl_positional, doc_positional

    spec_name = getattr(args, "spec_name", None)
    doc_name = (getattr(args, "doc", None) or "requirements.md")
    tpl_override = getattr(args, "template", None)

    if not spec_name and not (tpl_positional or doc_positional):
        output.error(
            "Template and document paths are required",
            hint=(
                "Usage: check-template-compliance.py <template> <doc> "
                "OR --spec-name NAME [--doc requirements.md] [--template PATH]"
            ),
        )

    if spec_name:
        doc_file = os.path.join(
            doc_dir_path("spec", spec_name, project_path), doc_name,
        )
        template_file = tpl_override or os.path.join(
            str(templates_dir(Path(project_path))),
            doc_name.replace(".md", "-template.md"),
        )
        return template_file, doc_file

    # Partial inputs — echo what's missing.
    if not tpl_positional:
        output.error(
            "Template file is required",
            hint="Pass a template path positionally or use --template PATH",
        )
    output.error(
        "Document file is required",
        hint="Pass a document path positionally or use --spec-name NAME",
    )


# Aggregator dispatches Group A rules that ride the generic envelope
# (``error-envelopes`` has its own block; ``import-paths-resolve`` is
# invoked via its own CLI). The single registry lives under
# ``internal_lints/_dispatch.py``; adding a new lint is one row there
# + one ``baselines.json::rules`` entry.
from internal_lints._dispatch import DISPATCH as _DISPATCH

_GROUP_A_DISPATCH = tuple(r for r in _DISPATCH if r.group == "A")


def _add_lint_flags(parser) -> None:
    """Register one ``--<rule-label>`` flag per Group A row."""
    for row in _GROUP_A_DISPATCH:
        parser.add_argument(
            f"--{row.rule_label}",
            action="store_true",
            dest=row.rule_id_attr,
            help=row.argparse_help or row.hint_text,
        )


def _dispatch_lint(args) -> None:
    """Dispatch a single AST/text lint chosen by the ``--<lint>`` flag.

    Loads the lint module, runs its ``analyze`` + ``compare_baseline``,
    and emits the same envelope shape every per-lint flag previously
    open-coded.
    """
    for row in _GROUP_A_DISPATCH:
        if not getattr(args, row.rule_id_attr):
            continue
        mod = importlib.import_module(row.module_path)
        findings = mod.analyze()
        diff = mod.compare_baseline(findings)
        ok = not diff["new"] and not diff["stale"]
        payload = {
            "ok": ok,
            "new_findings": diff["new"],
            "stale_entries": diff["stale"],
            "known": diff["known"],
            "findings": [f.to_payload() for f in findings],
        }
        message = (
            f"{row.rule_label} lint: {len(diff['new'])} new, "
            f"{len(diff['stale'])} stale, {len(diff['known'])} known"
        )
        from sdd_core.command_templates import build_baseline_refresh_command
        next_cmd = build_baseline_refresh_command(row.rule_label)
        if not ok:
            output.error(
                message,
                hint=row.hint_text,
                context=json.dumps({
                    "new": diff["new"], "stale": diff["stale"],
                }),
                next_action_command=next_cmd,
            )
        output.result(payload, message, exit_code=0)
        return


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("template_file", nargs="?", default=None,
                        help="Path to the template .md file")
    parser.add_argument("document_file", nargs="?", default=None,
                        help="Path to the document .md file")
    # Flag-form alternative. Registered via the shared helper so every
    # peer script reuses the same vocabulary.
    cli.add_document_selectors(
        parser, spec_name=True, doc=True, template=True,
    )
    parser.add_argument(
        "--skill-md", dest="skill_md", default=None,
        help="Check a SKILL.md for forbidden stale CLI literals",
    )
    _add_lint_flags(parser)
    parser.add_argument(
        "--strict", action="store_true",
        help=(
            "With --error-envelopes: fail when any call lacks a remediation. "
            "Default behaviour fails only when exemptions exceed max_exemptions() "
            "so the landing PR can ship while existing errors are worked off."
        ),
    )
    args = parser.parse_args()

    if any(getattr(args, r.rule_id_attr) for r in _GROUP_A_DISPATCH):
        _dispatch_lint(args)
        return

    if args.skill_md:
        from sdd_core.skill_md_rules import load_raw_rules

        findings = check_skill_md_literals(args.skill_md)
        raw_rules = load_raw_rules()
        findings.extend(_run_skill_md_lints(args.skill_md, raw_rules))
        if findings:
            output.partial(
                {"ok": False, "findings": findings, "file": args.skill_md},
                f"{len(findings)} SKILL.md compliance violation(s) in {args.skill_md}",
            )
        output.success(
            {"ok": True, "findings": [], "file": args.skill_md},
            "SKILL.md compliance check passed",
        )
        return

    project_path = paths.resolve_project_path(args)
    template_file, document_file = _resolve_paths(args, project_path)

    template_headings = _extract_headings(template_file)
    doc_headings = _extract_headings(document_file)

    norm_to_template = {_normalize_heading(h): h for h in template_headings}
    norm_to_doc = {_normalize_heading(h): h for h in doc_headings}

    template_set = set(norm_to_template.keys())
    doc_set = set(norm_to_doc.keys())

    present = template_set & doc_set
    missing = template_set - doc_set
    extra = doc_set - template_set
    total = len(template_set)
    found = len(present)

    if found == total:
        cr = ComplianceRating.COMPLIANT
    elif total - found <= 2:
        cr = ComplianceRating.PARTIAL
    else:
        cr = ComplianceRating.NON_COMPLIANT

    data = {
        "coverage": f"{found}/{total}",
        "rating": cr.name,
        "missing": sorted(norm_to_template[h] for h in missing),
        "extra": sorted(norm_to_doc[h] for h in extra),
        "template_file": template_file,
        "document_file": document_file,
    }

    msg = f"{cr.name} — {found}/{total} sections present"
    if cr == ComplianceRating.COMPLIANT:
        output.result(data, msg, exit_code=0)
    else:
        output.partial(data, msg)


if __name__ == "__main__":
    cli.run_main(main)
