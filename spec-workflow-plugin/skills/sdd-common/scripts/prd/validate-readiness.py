#!/usr/bin/env python3
"""Validate PRD readiness gate criteria.

Usage: validate-readiness.py --target <name> --gate <pre-requirements|pre-generation>
       validate-readiness.py --target <name> --gate <gate> --session-file
Exit code: 0 if structural criteria met, 1 if gaps found, 2 on usage error.

Gates:
  pre-requirements:
    - Problem statement exists and has 2+ sentences
    - Goals table has 2+ entries with non-placeholder columns
    - Non-goals section has 1+ entry with Reason column
  pre-generation:
    - All pre-requirements checks +
    - WHEN/THEN requirements present
    - All 6 NFR categories present
    - Open questions have Owner + Due Date + Blocks

Two input modes:
  Default (no --session-file): reads the full PRD document on disk.
  --session-file: reads .prd-session.json (progressive session state written
  during Steps 1-5 before the PRD document exists). Use during the
  conversational creation flow before Step 6.

Note: This script checks structural presence only. Judgment-based
quality (e.g., "is the metric attributable?") is assessed by the AI
per readiness-checks.md.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import os

from sdd_core import cli, handoffs, output
from skill_helpers import safe_open

# Mirrors workflow-graph.json `sdd-create-prd.context_needs`.
__sdd_context_needs__ = ("target", "workspace")
from prd.shared import (
    WHEN_THEN_RE, NFR_CATEGORIES, NFR_CATEGORY_KEYS, count_sentences,
    extract_section, check_nfr_presence,
)
from prd.checks import (
    check_goals_table,
    check_nongoals_reason,
    check_open_questions,
)
from prd.session_validators import (
    validate_problem_statement,
    validate_goals,
    validate_non_goals,
    validate_requirements_when_then,
    validate_nfr_categories,
    validate_open_questions as validate_session_oqs,
    scan_problem_statement_solution_markers,
)


def read_prd(feature_name: str, prd_name: str = "prd.md") -> str | None:
    """Read the PRD file for the given feature, return content or None.

    Checks discovery path first (canonical), falls back to legacy specs path.
    """
    discovery_path = os.path.join(".spec-workflow", "discovery", feature_name, prd_name)
    legacy_path = os.path.join(".spec-workflow", "specs", feature_name, prd_name)
    for prd_path in (discovery_path, legacy_path):
        if os.path.isfile(prd_path):
            with safe_open(prd_path) as f:
                return f.read()
    return None


def count_table_data_rows(section_text: str) -> int:
    """Count data rows in a markdown table (excluding header and separator)."""
    rows = 0
    past_header = False
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if all(c in "|- :" for c in stripped):
            past_header = True
            continue
        if past_header:
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if any(c and c not in ("", "#") for c in cells):
                rows += 1
        else:
            past_header = False
    return rows


def check_pre_requirements(content: str) -> list[str]:
    """Run pre-requirements gate checks."""
    gaps: list[str] = []

    problem = extract_section(content, r"problem\s+statement")
    problem_text = "\n".join(
        line for line in problem.splitlines()
        if line.strip() and not line.strip().startswith("[") and not line.strip().startswith("|")
    )
    sentence_count = count_sentences(problem_text)
    if sentence_count < 2:
        gaps.append(f"Problem statement has {sentence_count} sentence(s), need 2+")

    goals = extract_section(content, r"^3\.\s*goals|^goals$")
    goals_rows = count_table_data_rows(goals)
    if goals_rows < 2:
        gaps.append(f"Goals table has {goals_rows} data row(s), need 2+")
    else:
        gaps.extend(check_goals_table(content))

    nongoals = extract_section(content, r"non.?goals|^4\.\s")
    ng_rows = count_table_data_rows(nongoals)
    if ng_rows < 1:
        gaps.append("Non-goals section has no entries")
    else:
        gaps.extend(check_nongoals_reason(content))

    return gaps


def check_pre_generation(content: str) -> list[str]:
    """Run pre-generation gate checks (includes pre-requirements)."""
    gaps = check_pre_requirements(content)

    has_when_then = bool(WHEN_THEN_RE.search(content))
    if not has_when_then:
        gaps.append("No WHEN/THEN requirements found")

    gaps.extend(check_nfr_presence(content))

    gaps.extend(check_open_questions(content))

    return gaps


def _read_session_file(feature_name: str) -> dict | None:
    """Read .prd-session.json for the given feature, return dict or None."""
    session_path = os.path.join(
        ".spec-workflow", "discovery", feature_name, ".prd-session.json"
    )
    return output.safe_read_json(session_path)


def check_session_pre_requirements(session: dict) -> list[str]:
    """Validate session state for pre-requirements gate."""
    gaps: list[str] = []
    ps = session.get("problem_statement", {})
    gaps.extend(validate_problem_statement(ps.get("text", "")))
    gaps.extend(validate_goals(session.get("goals", [])))
    gaps.extend(validate_non_goals(session.get("non_goals", [])))
    return gaps


def scan_session_advisories(session: dict) -> list[dict]:
    """Return ``warn``-tier advisories for a session dict.

    Advisories never fail the gate — they surface drift the authoring
    agent can self-correct (e.g. a problem statement that names a
    solution). Mirrors ``ensure-healthy.py::_success_with_advisories``.
    """
    advisories: list[dict] = []
    ps_text = (session.get("problem_statement") or {}).get("text", "")
    markers = scan_problem_statement_solution_markers(ps_text)
    if markers:
        advisories.append({
            "name": "problem_statement_solution_marker",
            "severity": "warn",
            "detail": (
                "Problem statement names solution vocabulary: "
                + ", ".join(repr(m) for m in markers)
            ),
            "hint": (
                "Describe the user-visible problem; defer solution "
                "shape to the goals/requirements sections."
            ),
            "markers": list(markers),
        })
    return advisories


def check_session_pre_generation(session: dict) -> list[str]:
    """Validate session state for pre-generation gate."""
    gaps = check_session_pre_requirements(session)
    reqs = session.get("requirements", [])
    gaps.extend(validate_requirements_when_then(reqs))
    if gaps and gaps[-1] == "No WHEN/THEN requirements found":
        gaps[-1] = "No WHEN/THEN requirements found in session"
    gaps.extend(validate_nfr_categories(session.get("nfr_categories", {})))
    gaps.extend(validate_session_oqs(session.get("open_questions", [])))
    return gaps


def main() -> None:
    parser = cli.strict_parser("Validate PRD readiness gate criteria")
    cli.target_argument(parser, family="prd")
    parser.add_argument(
        "--gate",
        required=True,
        choices=["pre-requirements", "pre-generation"],
        help="Which readiness gate to check",
    )
    parser.add_argument("--prd-name", default="prd.md", help="PRD filename (default: prd.md)")
    parser.add_argument(
        "--session-file", action="store_true",
        help="Read .prd-session.json instead of the full PRD document",
    )
    args = parser.parse_args()
    ctx = cli.resolve_context(args, needs=__sdd_context_needs__)

    if args.session_file:
        session = _read_session_file(args.feature)
        if session is None:
            output.error(
                f"Session file not found for feature '{args.feature}'",
                hint="Run `sdd create prd` to start a session",
            )

        if args.gate == "pre-requirements":
            gaps = check_session_pre_requirements(session)
        else:
            gaps = check_session_pre_generation(session)
    else:
        content = read_prd(args.feature, args.prd_name)
        if content is None:
            output.error(
                f"PRD not found for feature '{args.feature}'",
                hint=f"Expected at .spec-workflow/discovery/{args.feature}/{args.prd_name}",
            )

        if args.gate == "pre-requirements":
            gaps = check_pre_requirements(content)
        else:
            gaps = check_pre_generation(content)

    advisories: list[dict] = []
    if args.session_file and session is not None:
        advisories = scan_session_advisories(session)

    data = {
        "gate": args.gate,
        "feature": args.feature,
        "input_mode": "session-file" if args.session_file else "prd-file",
        "result": "gaps_found" if gaps else "pass",
        "gaps": gaps,
        "gap_count": len(gaps),
    }
    if advisories:
        data["advisories"] = advisories

    if gaps:
        output.error(
            f"READINESS GAPS: {len(gaps)} issue(s) for gate '{args.gate}'",
            hint="Resolve the gaps before proceeding",
            context="\n".join(f"- {g}" for g in gaps),
        )
    else:
        suffix = (
            f" \u2014 advisories: {', '.join(a['name'] for a in advisories)}"
            if advisories else ""
        )
        output.success(
            data,
            f"GATE '{args.gate}' PASSED{suffix}",
            ctx=ctx,
            resolved_from=dict(ctx.resolved_from),
            handoffs=handoffs.handoffs_for(handoffs.current_script_id(), ctx),
        )


if __name__ == "__main__":
    cli.run_main(main)
