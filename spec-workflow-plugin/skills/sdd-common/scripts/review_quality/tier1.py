"""Tier 1 script execution — runs validation scripts as subprocesses."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Protocol

from pathlib import Path

from .registry import DOCUMENT_REGISTRY, TIER1_SCRIPT_SPECS, _STEERING_SIZE_LIMIT
from .paths import _SCRIPTS_ROOT as _SCRIPT_DIR, script_path as _script_path
from sdd_core.templates import resolve_template
from sdd_core import output
from sdd_core.compliance import ComplianceRating
from sdd_core.status import DocStatus


_RC_PASS = 0
_RC_FAIL = 1

_VALID_SCORES = frozenset({"pass", "partial", "fail"})


def _parse_per_check(stdout: str) -> dict[str, str] | None:
    """Parse per-check results from a validation script's stdout.

    Expects an ``output.result`` or ``output.success`` JSON envelope with
    ``data.checks`` mapping facet IDs to "pass"/"partial"/"fail".
    Returns None if stdout is empty or unparseable.
    """
    if not stdout or not stdout.strip():
        return None
    try:
        envelope = json.loads(stdout)
        checks = (envelope.get("data") or {}).get("checks")
        if isinstance(checks, dict) and all(
            v in _VALID_SCORES for v in checks.values()
        ):
            return checks
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


class SubprocessRunner(Protocol):
    def __call__(
        self, args: list[str], *, capture_output: bool,
        text: bool, cwd: str,
    ) -> subprocess.CompletedProcess: ...


def _parse_line_count(stdout: str) -> int | None:
    """Extract line count from count-effective-lines.py JSON output."""
    try:
        data = json.loads(stdout)
        return int(data["data"]["count"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def _parse_template_compliance(returncode: int, **_ignored: object) -> str:
    """Map exit code to tier1 compliance label via ComplianceRating enum."""
    try:
        return ComplianceRating(returncode).tier1_label
    except ValueError:
        return DocStatus.FAIL


def _compute_size_check(review_type: str, line_count: int | None) -> str | None:
    if review_type != "steering":
        return None
    if line_count is None:
        return DocStatus.INCOMPLETE
    return DocStatus.PASS if line_count <= _STEERING_SIZE_LIMIT else DocStatus.WARNING


def _default_size_check(review_type: str) -> str | None:
    return DocStatus.INCOMPLETE if review_type == "steering" else None


def _check_compliance_for_doc(
    doc_path: str,
    template_path: str | None,
    *,
    runner: SubprocessRunner | None = None,
) -> str:
    """Return tier1 compliance label for a single document."""
    if template_path is None or not os.path.isfile(doc_path):
        return DocStatus.INCOMPLETE
    _runner = runner or subprocess.run
    r = _runner(
        [sys.executable, _script_path("review/check-template-compliance.py"),
         template_path, doc_path],
        capture_output=True, text=True, cwd=_SCRIPT_DIR,
    )
    return _parse_template_compliance(r.returncode)


def _count_lines_for_doc(
    doc_path: str,
    *,
    runner: SubprocessRunner | None = None,
) -> int | None:
    """Return effective line count, or None if the file is missing/unparseable."""
    if not os.path.isfile(doc_path):
        return None
    _runner = runner or subprocess.run
    r = _runner(
        [sys.executable, _script_path("review/count-effective-lines.py"), "--file", doc_path],
        capture_output=True, text=True, cwd=_SCRIPT_DIR,
    )
    return _parse_line_count(r.stdout) if r.returncode == 0 else None


def run_tier1_scripts(
    doc_dir: str,
    review_type: str,
    reviewed_keys: list[str],
    spec_workflow_root: str,
    *,
    runner: SubprocessRunner | None = None,
) -> dict:
    """Run Tier 1 scripts and return results keyed by doc_key."""
    _runner = runner or subprocess.run
    reg = DOCUMENT_REGISTRY[review_type]
    doc_dir = os.path.abspath(doc_dir)
    results: dict[str, dict] = {}

    for doc_key in reviewed_keys:
        filename = reg["doc_files"][doc_key]
        doc_path = os.path.join(doc_dir, filename)
        doc_stem = reg["doc_stems"][doc_key]

        resolved = resolve_template(doc_stem, Path(spec_workflow_root).parent)
        template_path = str(resolved.path) if resolved else None
        template_compliance = _check_compliance_for_doc(
            doc_path, template_path, runner=_runner,
        )

        line_count = _count_lines_for_doc(doc_path, runner=_runner)
        if not os.path.isfile(doc_path):
            size_check = _default_size_check(review_type)
        else:
            size_check = _compute_size_check(review_type, line_count) if line_count is not None else _default_size_check(review_type)

        results[doc_key] = {
            "template_compliance": template_compliance,
            "line_count": line_count,
            "size_check": size_check,
            "tier1_facets": {},
        }

    for script_name in reg["tier1_scripts"]:
        spec = TIER1_SCRIPT_SPECS[script_name]
        if "doc_args" not in spec:
            # Lint-shaped entries (no ``doc_args``) are owned by the lint
            # aggregator, not this per-doc runner. Skipping keeps this
            # loop single-purpose.
            continue
        req_docs = spec["doc_args"]
        if not all(d in reviewed_keys for d in req_docs):
            continue
        script_args: list[str] = []
        all_present = True
        for d in req_docs:
            doc_path = os.path.join(doc_dir, reg["doc_files"][d])
            if not os.path.isfile(doc_path):
                all_present = False
                break
            script_args.append(doc_path)
        if not all_present:
            continue
        r = _runner(
            [sys.executable, _script_path(script_name)] + script_args,
            capture_output=True, text=True, cwd=_SCRIPT_DIR,
        )
        if r.returncode not in (_RC_PASS, _RC_FAIL):
            output.warn(
                f"{script_name} exited with unexpected code {r.returncode};"
                " setting affected facets to 'na'"
            )
            score = "na"
        else:
            score = "pass" if r.returncode == _RC_PASS else "fail"

        per_check = _parse_per_check(r.stdout)
        primary_doc = spec.get("attribution_doc", req_docs[0])
        if primary_doc in results:
            for facet_id in spec["covers"]:
                if per_check and facet_id in per_check:
                    results[primary_doc]["tier1_facets"][facet_id] = per_check[facet_id]
                else:
                    results[primary_doc]["tier1_facets"][facet_id] = score

    return results
