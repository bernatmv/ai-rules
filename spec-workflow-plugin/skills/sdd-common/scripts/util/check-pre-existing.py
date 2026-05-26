#!/usr/bin/env python3
"""Check if a task's implementation already exists (verification-only detection).

Usage: check-pre-existing.py --spec-name NAME --task-id ID [--workspace PATH]

Returns JSON (exit 0 always):
  { "pre_existing": true/false, "evidence": "...", "leverage_files": {...}, "test_result": ... }
"""
from __future__ import annotations
import _bootstrap  # noqa: F401

import argparse
import json
import os
import re
import sys

from sdd_core import paths, tasks, output, cli
from sdd_core.matchers import WordMatcher
from sdd_core.security.subprocess_safe import safe_run_test
from sdd_core.tasks import is_header

_PAREN_QUALIFIER = re.compile(r"\s*\([^)]*\)\s*$")

_OPTIONAL_KEYWORDS = frozenset(("if exists", "optional", "when present"))


def _clean_leverage_path(raw: str) -> tuple[str, bool]:
    """Strip parenthetical qualifiers; return (cleaned_path, is_optional)."""
    m = _PAREN_QUALIFIER.search(raw)
    if m:
        qualifier = m.group(0).lower()
        optional = any(kw in qualifier for kw in _OPTIONAL_KEYWORDS)
        return raw[:m.start()].strip(), optional
    return raw.strip(), False


VERIFICATION_WORDS = WordMatcher(
    ["verify", "confirm", "validate existing", "test existing",
     "verify and test", "confirm and test"],
    boundary="word",
)

TEST_RUNNER_WORDS = WordMatcher(
    ["pytest", "python3 -m pytest", "python -m unittest", "npm test",
     "npx jest", "go test"],
    boundary="none",
)


def _extract_leverage_files(
    task_data: dict, project_path: str = "",
) -> list[tuple[str, bool, str | None]]:
    """Extract file paths from _Leverage.

    Returns ``[(path, is_optional, validation_reason_or_None), ...]``.
    A non-None ``validation_reason`` (e.g. ``"invalid path"``) signals
    that the path failed ``paths.validate_path`` — callers surface
    these in the ``missing`` list regardless of ``is_optional``.
    """
    leverage = task_data.get("metadata", {}).get("Leverage", "")
    if not leverage:
        return []
    from pathlib import Path as _Path
    files: list[tuple[str, bool, str | None]] = []
    root = _Path(project_path) if project_path else None
    for part in leverage.split(","):
        part = part.strip().strip("`")
        if not part or part.startswith("("):
            continue
        path_val, optional = _clean_leverage_path(part)
        if not path_val:
            continue
        reason: str | None = None
        if root is not None:
            try:
                paths.validate_path(path_val, root)
            except ValueError:
                reason = "invalid path"
        files.append((path_val, optional, reason))
    return files


def _extract_success_text(task_data: dict) -> str:
    """Extract Success criteria text from task lines."""
    lines = task_data.get("lines", [])
    in_success = False
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- _Prompt:") or stripped.startswith("**Success"):
            in_success = "Success" in stripped or "success" in stripped
            if in_success:
                result_lines.append(stripped)
            continue
        if in_success:
            if stripped.startswith("- _") or stripped.startswith("**"):
                break
            result_lines.append(stripped)
    return "\n".join(result_lines)


def _detect_test_command(text: str) -> str | None:
    """Detect a test runner command in the text."""
    m = TEST_RUNNER_WORDS.search(text)
    if not m:
        return None
    matched = m.group(0)
    start = text.find(matched)
    end = text.find("\n", start)
    if end == -1:
        end = len(text)
    line = text[start:end].strip()
    if line.startswith("`"):
        line = line.strip("`")
    return line


def _run_test_command(command: str, project_path: str) -> dict:
    """Run a test command via :func:`safe_run_test`.

    Document-sourced commands pass through an argv allowlist + shell-
    metacharacter denylist; unsafe strings never reach the OS. See
    ``sdd_core.security.subprocess_safe`` for the contract.
    """
    return safe_run_test(command, project_path=project_path).to_dict()


def check_single_task(task_data: dict, project_path: str) -> dict:
    """Check a single task for pre-existing implementation. Returns result dict."""
    prompt_text = "\n".join(task_data.get("lines", []))

    if not VERIFICATION_WORDS.search(prompt_text):
        return {
            "pre_existing": False,
            "evidence": "Task prompt does not match verification keywords",
            "leverage_files": {"found": [], "missing": []},
            "test_result": None,
        }

    leverage_files = _extract_leverage_files(task_data, project_path)
    if not leverage_files:
        return {
            "pre_existing": False,
            "evidence": "No _Leverage field — cannot determine",
            "leverage_files": {"found": [], "missing": []},
            "test_result": None,
        }

    found = []
    missing = []
    for f, optional, reason in leverage_files:
        if reason == "invalid path":
            # Invalid paths always surface in missing — containment
            # failures never satisfy "pre-existing" even when optional.
            missing.append(f)
            continue
        full = os.path.join(project_path, f)
        if os.path.exists(full):
            found.append(f)
        elif optional:
            found.append(f)
        else:
            missing.append(f)

    if missing:
        return {
            "pre_existing": False,
            "evidence": f"{len(missing)} leverage file(s) missing: {', '.join(missing)}",
            "leverage_files": {"found": found, "missing": missing},
            "test_result": None,
        }

    success_text = _extract_success_text(task_data)
    test_cmd = _detect_test_command(prompt_text) or _detect_test_command(success_text)

    test_result = None
    if test_cmd:
        test_result = _run_test_command(test_cmd, project_path)
        if test_result.get("error"):
            return {
                "pre_existing": False,
                "evidence": f"Test command failed to execute: {test_result['error']}",
                "leverage_files": {"found": found, "missing": missing},
                "test_result": test_result,
            }
        if test_result.get("failed", 0) > 0:
            return {
                "pre_existing": False,
                "evidence": f"Tests have failures: {test_result['failed']} failed, {test_result['passed']} passed",
                "leverage_files": {"found": found, "missing": missing},
                "test_result": test_result,
            }

    evidence_parts = [f"All {len(found)} leverage file(s) exist"]
    if test_result and test_result.get("passed", 0) > 0:
        evidence_parts.append(f"{test_result['passed']} tests passing (0 failures)")
        pre_existing = True
    elif test_result:
        evidence_parts.append("Tests ran but none passed")
        pre_existing = False
    else:
        evidence_parts.append("No test command detected — determined by file existence + verification keywords")
        pre_existing = True

    return {
        "pre_existing": pre_existing,
        "evidence": ". ".join(evidence_parts) + ".",
        "leverage_files": {"found": found, "missing": missing},
        "test_result": test_result,
    }


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("--spec-name", required=True, type=cli.name_type("spec-name"))
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--batch-check", action="store_true",
                        help="Check ALL tasks, return per-task results array")
    args = parser.parse_args()

    if not args.task_id and not args.batch_check:
        output.error(
            "Either --task-id or --batch-check is required",
            hint="Use --task-id ID for single task, or --batch-check for all tasks",
        )

    project_path = paths.resolve_project_path(args)
    root = paths.require_workflow_root(project_path)

    tasks_file = paths.spec_dir(root, args.spec_name) / "tasks.md"
    if not tasks_file.exists():
        output.error(f"tasks.md not found for spec: {args.spec_name}")

    parsed_tasks = tasks.parse_tasks(tasks_file.read_text())

    if args.batch_check:
        results = []
        non_pre_existing = []
        for task_data in parsed_tasks:
            if is_header(task_data):
                continue
            result = check_single_task(task_data, project_path)
            entry = {"task_id": task_data["id"], **result}
            results.append(entry)
            if not result["pre_existing"]:
                non_pre_existing.append(task_data["id"])

        all_pre = len(non_pre_existing) == 0 and len(results) > 0
        output.success({
            "all_pre_existing": all_pre,
            "results": results,
            "non_pre_existing": non_pre_existing,
        }, f"Batch check: {len(results)} tasks, {'all pre-existing' if all_pre else f'{len(non_pre_existing)} not pre-existing'}")
        return

    task = tasks.get_task_by_id(parsed_tasks, args.task_id)
    if not task:
        output.error(f"Task '{args.task_id}' not found in spec '{args.spec_name}'")

    result = check_single_task(task, project_path)
    pre_existing = result["pre_existing"]
    output.success(result, f"Pre-existing check: {'yes' if pre_existing else 'no'}")


if __name__ == "__main__":
    cli.run_main(main)
