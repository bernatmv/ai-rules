#!/usr/bin/env python3
"""Detect document state for any SDD category.

Reports existence (disk + git), effective line counts, sibling context,
and recommends the appropriate creation/collision action.

Generic — works for steering, spec, and discovery categories.
--category controls path resolution (filesystem concept).
--registry-type controls DOCUMENT_REGISTRY lookup (scoring/structure concept).
When --registry-type is omitted it is inferred from --category
(discovery → prd; others are identity).

Usage:
  detect-doc-state.py --category steering --target-doc product.md --workspace .
  detect-doc-state.py --category spec --target-name my-feature --workspace .
  detect-doc-state.py --category discovery --target-name my-feature --target-doc prd.md

Exit code: 0 always (result in JSON envelope).
"""
from __future__ import annotations

import _bootstrap  # noqa: F401
import argparse
import os
from pathlib import Path

from sdd_core import cli, git, output, paths
from sdd_core.paths import doc_dir_path
from sdd_core.doc_config import DOCUMENT_REGISTRY
from sdd_core.category_registry import REVIEW_TYPE_TO_CATEGORY
from sdd_core import reference_ledger
from sdd_core import detect_doc_state_cache as _cache


__sdd_manifest__ = {
    "summary": "Detect document state and recommend a creation/collision action",
    "verbs": [
        "--category {steering|spec|discovery} --target-doc <filename>",
        "--category {spec|discovery} --target-name <name> --target-doc <filename>",
    ],
    "aliases": {},
    "flags": [
        "--category", "--target-name", "--spec-name", "--target-doc",
        "--workspace", "--registry-type",
    ],
}
from skill_helpers import iter_effective_lines
from review_quality.constants import GIT_TIMEOUT_SECS


USER_GATHERING_RULES: dict[tuple[str, str], dict] = {
    ("steering", "product_md"): {
        "required": True,
        "reason_required": (
            "Product vision and goals cannot be fully inferred from code. "
            "Present inferred context summary and ask user to confirm or adjust."
        ),
    },
    ("steering", "tech_md"): {
        "required": False,
        "reason_not_required": (
            "Technology stack is inferable from codebase analysis. "
            "User confirmation is helpful but not mandatory."
        ),
    },
    ("steering", "structure_md"): {
        "required": False,
        "reason_not_required": (
            "Directory structure is directly observable from the codebase."
        ),
    },
    ("spec", "requirements_md"): {
        "required": True,
        "reason_required": (
            "Feature requirements reflect user/business intent that "
            "cannot be inferred from code alone."
        ),
    },
    ("spec", "ui_design_md"): {
        "required": True,
        "reason_required": (
            "UI/UX design requires designer or user input on "
            "layout, interactions, and visual decisions."
        ),
    },
    ("spec", "design_md"): {
        "required": False,
        "reason_not_required": (
            "Technical design can be derived from approved requirements "
            "and codebase analysis."
        ),
    },
    ("spec", "tasks_md"): {
        "required": False,
        "reason_not_required": (
            "Tasks are derived from approved design document."
        ),
    },
    ("prd", "prd_md"): {
        "required": True,
        "reason_required": (
            "PRD captures problem definition and goals that must "
            "come from the product owner."
        ),
    },
}

_CATEGORY_ALIASES: dict[str, str] = {
    rtype: reg["category"]
    for rtype, reg in DOCUMENT_REGISTRY.items()
    if reg.get("category") and reg["category"] != rtype
}

_VALID_CATEGORIES = ("spec", "steering", "discovery") + tuple(_CATEGORY_ALIASES)


def _check_git_history(doc_path: str, project_path: str) -> bool:
    """Check if a file exists in git history. Returns bool."""
    rel = os.path.relpath(doc_path, project_path)
    return git.log_oneline(rel, cwd=Path(project_path), timeout=GIT_TIMEOUT_SECS)


def _count_lines(filepath: str) -> int | None:
    """Count effective lines if file exists, None otherwise."""
    if not os.path.isfile(filepath):
        return None
    return sum(1 for _ in iter_effective_lines(filepath))


def _recommend_action(
    target_doc_state: dict | None,
    summary: dict,
    category: str,
) -> tuple[str, str]:
    """Pure function: determine recommended_action from document state."""
    if target_doc_state is None:
        if summary["no_docs_exist"]:
            return "create_all", "No docs exist. Proceed with creation workflow."
        if summary["all_required_exist"]:
            return "collision_prompt", "All required docs exist. Present collision prompt."
        return "create_missing", f"Create missing docs: {summary['missing_required']}"

    if target_doc_state["exists_on_disk"]:
        return "collision_prompt", "Target doc exists on disk. Present collision prompt."
    if target_doc_state["exists_in_git"]:
        return (
            "recreate_prompt",
            "Target doc has a prior version in git. Present recreate choice: "
            "(a) restore + review, (b) create fresh, (c) cancel.",
        )
    return "create_fresh", "No prior version exists. Create from template."


def _collision_type(summary: dict, target_doc_state: dict | None) -> str:
    """Classify the collision scenario."""
    if summary["no_docs_exist"]:
        return "none"
    if summary["all_required_exist"]:
        return "full_set"
    if target_doc_state and target_doc_state["exists_on_disk"]:
        return "target_exists"
    return "partial_set"


_CATEGORY_TO_REVIEW_TYPE: dict[str, str] = {
    cat: rtype for rtype, cat in REVIEW_TYPE_TO_CATEGORY.items() if rtype != cat
}


def _infer_registry_type(category: str) -> str:
    """Infer the DOCUMENT_REGISTRY key from a pipeline category."""
    return _CATEGORY_TO_REVIEW_TYPE.get(category, category)


def _resolve_category(raw: str) -> str:
    """Resolve a CLI category value, applying aliases from DOCUMENT_REGISTRY."""
    return _CATEGORY_ALIASES.get(raw, raw)


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument(
        "--category", required=True,
        choices=_VALID_CATEGORIES,
        help="Pipeline category for path resolution",
    )
    parser.add_argument(
        "--registry-type", default=None,
        choices=list(DOCUMENT_REGISTRY),
        help="Registry type for doc structure (default: inferred from category)",
    )
    parser.add_argument(
        "--target-name", default="",
        type=cli.name_type("target-name"),
        help="Spec name or discovery project name (steering uses implicit name)",
    )
    parser.add_argument(
        "--target-doc", default=None,
        help="Specific doc to focus on (e.g. product.md). If omitted, reports on all.",
    )
    parser.add_argument(
        "--gate-id", default=None,
        help=(
            "Reserved pass-through flag for pipeline integration. "
            "Detection is content-hash driven and does not branch on gate id — "
            "accepted so a pipeline envelope that appends --gate-id to every "
            "precondition does not fail on this script."
        ),
    )
    args = parser.parse_args()

    category = _resolve_category(args.category)
    registry_type = args.registry_type or _infer_registry_type(category)
    target_name = args.target_name or category
    project_path = paths.resolve_project_path(args)
    target_doc = args.target_doc

    registry = DOCUMENT_REGISTRY.get(registry_type)
    if not registry:
        output.error(
            f"Unknown registry type '{registry_type}'",
            hint=f"Available: {', '.join(sorted(DOCUMENT_REGISTRY))}",
        )

    doc_keys = registry["doc_keys"]
    doc_files = registry["doc_files"]
    optional_keys = set(registry.get("optional_doc_keys") or [])
    doc_dir = doc_dir_path(category, target_name, project_path)

    # Content-hash cache short-circuit — if every target doc's SHA is
    # unchanged since the last detection, serve the cached payload in
    # <50 ms instead of re-walking the filesystem. The cache miss path
    # below writes the fresh payload back under the new hash.
    all_keys_for_cache = (
        list(doc_keys) + [k for k in optional_keys if k not in doc_keys]
    )
    cache_paths = [
        os.path.join(doc_dir, doc_files[dk])
        for dk in all_keys_for_cache
        if doc_files.get(dk)
    ]
    state_sha = _cache.compute_state_sha(cache_paths)
    cached_payload = _cache.load_cached(
        project_path, category, target_name, state_sha,
    )
    if cached_payload is not None:
        cached_payload = dict(cached_payload)
        cached_payload["cache_hit"] = True
        cached_payload["cache_sha"] = state_sha
        if args.gate_id:
            cached_payload["cached_for_gate_id"] = args.gate_id
        try:
            reference_ledger.append(
                category=category,
                target_name=target_name,
                script="util/detect-doc-state.py",
                doc=target_doc,
                project_path=project_path,
                extra={
                    "recommended_action": cached_payload.get(
                        "recommended_action"
                    ),
                    "cache_hit": True,
                },
            )
        except Exception:  # noqa: BLE001
            pass
        output.success(
            cached_payload,
            f"Document state served from cache for {category}",
        )
        return

    docs_report: dict[str, dict] = {}
    target_doc_key = None

    all_keys = all_keys_for_cache
    for dk in all_keys:
        filename = doc_files.get(dk, "")
        if not filename:
            continue
        full_path = os.path.join(doc_dir, filename)
        exists_on_disk = os.path.isfile(full_path)
        exists_in_git = _check_git_history(full_path, project_path) if not exists_on_disk else True
        effective_lines = _count_lines(full_path)
        is_target = target_doc is not None and filename == target_doc

        if is_target:
            target_doc_key = dk

        docs_report[filename] = {
            "doc_key": dk,
            "exists_on_disk": exists_on_disk,
            "exists_in_git": exists_in_git if not exists_on_disk else True,
            "effective_lines": effective_lines,
            "is_target": is_target,
            "is_optional": dk in optional_keys,
        }

    required_docs = [fn for fn, d in docs_report.items() if not d["is_optional"]]
    exist_on_disk = [fn for fn, d in docs_report.items() if d["exists_on_disk"]]
    exist_in_git = [fn for fn, d in docs_report.items() if d["exists_in_git"]]
    missing_required = [fn for fn in required_docs if fn not in exist_on_disk]

    target_state = None
    if target_doc and target_doc in docs_report:
        target_state = docs_report[target_doc]

    summary = {
        "total_expected": len(required_docs),
        "exist_on_disk": len(exist_on_disk),
        "exist_in_git": len(exist_in_git),
        "missing_required": missing_required,
        "target_exists": target_state["exists_on_disk"] if target_state else False,
        "target_in_git": target_state["exists_in_git"] if target_state else False,
        "has_sibling_context": any(
            d["exists_on_disk"] and not d["is_target"]
            for d in docs_report.values()
        ),
        "all_required_exist": len(missing_required) == 0,
        "no_docs_exist": len(exist_on_disk) == 0,
    }

    action, action_note = _recommend_action(target_state, summary, category)
    ctype = _collision_type(summary, target_state)

    gathering_key = target_doc_key or (doc_keys[0] if doc_keys else None)
    rule = USER_GATHERING_RULES.get((registry_type, gathering_key), {}) if gathering_key else {}
    context_available = [
        f"{fn} ({d['effective_lines']} lines)"
        for fn, d in docs_report.items()
        if d["exists_on_disk"] and d["effective_lines"] and not d.get("is_target")
    ]
    user_gathering = {
        "required": rule.get("required", False),
        "reason": rule.get("reason_required") or rule.get("reason_not_required", ""),
        "context_available": context_available,
    }

    result = {
        "category": category,
        "target_name": target_name,
        "doc_dir": os.path.relpath(doc_dir, project_path) if project_path else doc_dir,
        "docs": docs_report,
        "summary": summary,
        "recommended_action": action,
        "recommended_action_note": action_note,
        "collision_type": ctype,
        "user_gathering": user_gathering,
        "cache_hit": False,
        "cache_sha": state_sha,
    }
    _cache.store(project_path, category, target_name, state_sha, result)

    # Record a ledger entry so the launch preconditions gate can verify
    # this precondition was satisfied.
    try:
        reference_ledger.append(
            category=category,
            target_name=target_name,
            script="util/detect-doc-state.py",
            doc=target_doc,
            project_path=project_path,
            extra={"recommended_action": action},
        )
    except Exception:  # noqa: BLE001 — advisory ledger; never block success
        pass

    output.success(result, f"Document state detected for {category}")


if __name__ == "__main__":
    cli.run_main(main)
