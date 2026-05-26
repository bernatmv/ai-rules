"""Unified finding taxonomy — one ``Finding`` dataclass, one counter.

# lint: canonical-owner — review_quality.findings owns the
# ``FindingSource`` literal alias. The string value happens to match
# the sub-agent input key ``cross_validation``, but the two are
# semantically distinct: the input key names the artifact block, the
# FindingSource value names the finding-source bucket. The alias is
# canonical here so downstream consumers import the constant
# (``FINDING_SOURCE_CROSS_VALIDATION``) instead of restating the
# literal.

Every finding surfaced by the review pipeline collapses to a single
``Finding`` record keyed by ``source``:

- ``facet_issue`` — per-facet issues (``documents[*].facets[*].issues``).
- ``cross_validation`` — cross-document findings.
- ``tier1_check`` — advisory signals from Tier 1 checks
  (``template_compliance``, ``size_check``,
  ``cross_validation.status``).

The public surface is two helpers:

- :func:`collect_findings` — flatten an artifact into a ``list[Finding]``.
- :func:`findings_by_source_severity` — bucket by ``{source: {severity: count}}``.

:func:`actionable_finding_count` isolates the subset that routes into
the fix loop (facet critical/warning + cross-validation conflicts).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from sdd_core.review_input import INPUT_KEY_CROSS_VALIDATION

__all__ = [
    "FindingSource",
    "Finding",
    "FINDING_SOURCE_FACET_ISSUE",
    "FINDING_SOURCE_CROSS_VALIDATION",
    "FINDING_SOURCE_TIER1_CHECK",
    "collect_findings",
    "findings_by_source_severity",
    "actionable_finding_count",
    "advisory_finding_count",
    "count_findings_in_artifact",
    "count_advisories_in_artifact",
    "findings_present",
]


# Canonical ``FindingSource`` literal values, exported as constants so
# call-sites can import the names instead of repeating the bare string
# (which collides with the sub-agent input key ``cross_validation``).
FINDING_SOURCE_FACET_ISSUE: str = "facet_issue"
FINDING_SOURCE_CROSS_VALIDATION: str = "cross_validation"
FINDING_SOURCE_TIER1_CHECK: str = "tier1_check"

FindingSource = Literal["facet_issue", "cross_validation", "tier1_check"]
FindingSeverity = Literal[
    "critical", "warning", "suggestion", "advisory",
    "duplication", "conflict", "gap", "drift",
]


@dataclass(frozen=True)
class Finding:
    source: FindingSource
    severity: str
    doc_key: Optional[str]
    pair: Optional[tuple[str, str]]
    summary: str
    detail: Optional[str] = None


_FACET_SEVERITIES = ("critical", "warning", "suggestion")


def _collect_facet_issues(documents: dict) -> list[Finding]:
    results: list[Finding] = []
    if not isinstance(documents, dict):
        return results
    for doc_key, doc in documents.items():
        if not isinstance(doc, dict):
            continue
        for facet in doc.get("facets", []) or []:
            if not isinstance(facet, dict):
                continue
            issues = facet.get("issues") or {}
            facet_label = facet.get("name") or facet.get("id") or doc_key
            for sev in _FACET_SEVERITIES:
                count = int(issues.get(sev, 0) or 0)
                for _ in range(count):
                    results.append(Finding(
                        source="facet_issue",
                        severity=sev,
                        doc_key=doc_key,
                        pair=None,
                        summary=f"{doc_key}: {facet_label}",
                    ))
    return results


def _collect_cross_validation(cv: dict) -> list[Finding]:
    results: list[Finding] = []
    if not isinstance(cv, dict):
        return results

    for finding in (cv.get("findings") or []):
        if not isinstance(finding, dict):
            continue
        ftype = str(finding.get("type") or "suggestion")
        summary = str(
            finding.get("summary")
            or finding.get("pair") or ""
        )
        pair = None
        raw_pair = finding.get("pair")
        if isinstance(raw_pair, (list, tuple)) and len(raw_pair) == 2:
            pair = (str(raw_pair[0]), str(raw_pair[1]))
        results.append(Finding(
            source=FINDING_SOURCE_CROSS_VALIDATION,
            severity=ftype,
            doc_key=None,
            pair=pair,
            summary=summary,
        ))

    for pair_key, pair_data in (cv.get("pairs") or {}).items():
        if not isinstance(pair_data, dict):
            continue
        pair_tuple = None
        if isinstance(pair_key, str) and "_x_" in pair_key:
            parts = pair_key.split("_x_", 1)
            if len(parts) == 2:
                pair_tuple = (parts[0], parts[1])
        for finding in pair_data.get("findings", []) or []:
            if not isinstance(finding, dict):
                continue
            ftype = str(finding.get("type") or "suggestion")
            results.append(Finding(
                source=FINDING_SOURCE_CROSS_VALIDATION,
                severity=ftype,
                doc_key=None,
                pair=pair_tuple,
                summary=str(finding.get("summary") or pair_key),
            ))
    return results


def _collect_tier1_advisories(artifact: dict) -> list[Finding]:
    results: list[Finding] = []
    documents = artifact.get("documents") if isinstance(artifact, dict) else None
    if isinstance(documents, dict):
        for doc_key, doc in documents.items():
            if not isinstance(doc, dict):
                continue
            tc = doc.get("template_compliance")
            if isinstance(tc, str) and tc == "FAIL":
                results.append(Finding(
                    source="tier1_check",
                    severity="advisory",
                    doc_key=doc_key,
                    pair=None,
                    summary=f"{doc_key}: template_compliance FAIL",
                ))
            sc = doc.get("size_check")
            if isinstance(sc, str) and sc in {"FAIL", "WARNING"}:
                results.append(Finding(
                    source="tier1_check",
                    severity="advisory",
                    doc_key=doc_key,
                    pair=None,
                    summary=f"{doc_key}: size_check {sc}",
                ))
    cv = artifact.get(INPUT_KEY_CROSS_VALIDATION) if isinstance(artifact, dict) else None
    if isinstance(cv, dict):
        status = cv.get("status")
        if isinstance(status, str) and status in {"NEEDS_WORK", "FAIL"}:
            results.append(Finding(
                source="tier1_check",
                severity="advisory",
                doc_key=None,
                pair=None,
                summary=f"cross_validation.status {status}",
            ))
    return results


def collect_findings(quality_artifact: dict) -> list[Finding]:
    """Flatten every finding in the artifact into one :class:`Finding` list.

    Partial artifacts (missing ``documents`` / ``cross_validation``)
    return an empty list — never raise, so consumers can tolerate
    incomplete inputs.
    """
    if not isinstance(quality_artifact, dict):
        return []
    documents = quality_artifact.get("documents") or {}
    cv = quality_artifact.get(INPUT_KEY_CROSS_VALIDATION) or {}
    return (
        _collect_facet_issues(documents)
        + _collect_cross_validation(cv)
        + _collect_tier1_advisories(quality_artifact)
    )


def findings_by_source_severity(findings: list[Finding]) -> dict:
    """Return ``{source: {severity: count}}`` buckets.

    The envelope carries this dict verbatim; scalar totals are derived
    at the call site via :func:`actionable_finding_count` when needed.
    """
    buckets: dict[str, dict[str, int]] = {}
    for f in findings:
        buckets.setdefault(f.source, {})
        buckets[f.source][f.severity] = buckets[f.source].get(f.severity, 0) + 1
    return buckets


def actionable_finding_count(findings: list[Finding]) -> int:
    """Count only findings that should route into the fix loop.

    Actionable = facet_issue (critical | warning) + cross_validation
    conflicts. Duplications / suggestions / tier1 advisories are
    informational — they surface in the summary but do not route into
    the fix loop.
    """
    actionable = 0
    for f in findings:
        if f.source == "facet_issue" and f.severity in ("critical", "warning"):
            actionable += 1
        elif f.source == FINDING_SOURCE_CROSS_VALIDATION and f.severity == "conflict":
            actionable += 1
    return actionable


def advisory_finding_count(findings: list[Finding]) -> int:
    """Count findings that surface to the operator without routing the fix loop.

    Advisory = every finding that :func:`actionable_finding_count` does
    not include. Currently: facet_issue suggestions, cross_validation
    non-conflict findings (suggestion / duplication / drift / gap) and
    every tier1_check advisory.

    Pairs with :func:`actionable_finding_count` so the status tuple
    ``(actionable, advisory)`` is exhaustive over the
    :func:`collect_findings` output.
    """
    advisory = 0
    for f in findings:
        if f.source == "facet_issue" and f.severity in ("critical", "warning"):
            continue
        if f.source == FINDING_SOURCE_CROSS_VALIDATION and f.severity == "conflict":
            continue
        advisory += 1
    return advisory


# ---------------------------------------------------------------------------
# Public counters for review envelopes.
# ---------------------------------------------------------------------------


def count_findings_in_artifact(artifact: dict | None) -> int:
    """Return the actionable finding count for a quality artifact.

    Returns ``-1`` when the artifact is missing or carries neither
    ``documents`` nor ``cross_validation`` so callers can distinguish
    "nothing scored" from "zero findings". Mirrors the contract of the
    legacy ``_count_artifact_findings_from_data`` helper.
    """
    if not artifact or not isinstance(artifact, dict):
        return -1
    if not artifact.get("documents") and not artifact.get(INPUT_KEY_CROSS_VALIDATION):
        return -1
    return actionable_finding_count(collect_findings(artifact))


def count_advisories_in_artifact(artifact: dict | None) -> int:
    """Return the advisory finding count for a quality artifact.

    Returns ``0`` when the artifact is missing or carries neither
    ``documents`` nor ``cross_validation`` — advisories never block
    routing, so the "nothing scored" sentinel collapses to "no
    advisories" rather than mirroring the actionable ``-1`` distinction.
    """
    if not artifact or not isinstance(artifact, dict):
        return 0
    if not artifact.get("documents") and not artifact.get(INPUT_KEY_CROSS_VALIDATION):
        return 0
    return advisory_finding_count(collect_findings(artifact))


def findings_present(artifact: dict | None) -> bool:
    """Return ``True`` iff the artifact carries at least one actionable finding.

    Treats the "nothing scored" sentinel (``-1``) as ``False`` so
    callers see a clean three-state model: missing → False, zero
    findings → False, one-or-more findings → True.
    """
    return count_findings_in_artifact(artifact) > 0
