"""Cross-validation block construction and staleness invalidation."""
from __future__ import annotations

from sdd_core.review_input import INPUT_KEY_CROSS_VALIDATION
from sdd_core.status import DocStatus

from .registry import is_valid_finding

MIN_REVIEWED_KEYS_FOR_CV = 2
FINDING_TYPE_GAP = "gap"
FINDING_STATUS_MISSING = "missing"
FINDING_TYPE_ADVISORY = "advisory_cross_validation"


def collect_prior_advisories(prior_cv: dict | None) -> list[dict]:
    """Return every ``advisory_cross_validation`` finding in *prior_cv*.

    Walks both the flat ``findings`` array (which carries an injected
    ``pair`` field) and each pair's per-pair ``findings`` list. De-dupes
    by ``(pair, type, summary)`` tuple so merging a flat + per-pair
    representation of the same advisory yields one entry on output.
    """
    if not isinstance(prior_cv, dict):
        return []
    seen: set[tuple] = set()
    collected: list[dict] = []

    def _add(pair_key: str, finding: dict) -> None:
        if not isinstance(finding, dict):
            return
        if finding.get("type") != FINDING_TYPE_ADVISORY:
            return
        summary = str(finding.get("summary") or finding.get("description") or "")
        key = (pair_key, summary)
        if key in seen:
            return
        seen.add(key)
        normalised = dict(finding)
        normalised.setdefault("pair", pair_key)
        collected.append(normalised)

    for f in prior_cv.get("findings") or []:
        _add(str(f.get("pair", "")) if isinstance(f, dict) else "", f)
    pairs = prior_cv.get("pairs") or {}
    if isinstance(pairs, dict):
        for pair_key, pair_data in pairs.items():
            if not isinstance(pair_data, dict):
                continue
            for f in pair_data.get("findings") or []:
                _add(pair_key, f)
    return collected


def _has_issues(pair_data: dict) -> bool:
    """True if the pair has any conflicts, duplications, or gaps."""
    return bool(
        pair_data.get("conflicts", 0)
        or pair_data.get("duplications", 0)
        or pair_data.get("gaps", 0)
    )


def find_stale_cross_validation(quality_data: dict, doc_stem: str) -> list[str]:
    """Return pairs with stale 'missing' gap findings referencing the given doc."""
    cross_val = quality_data.get(INPUT_KEY_CROSS_VALIDATION) or {}
    findings = cross_val.get("findings", [])
    stale = []
    for finding in findings:
        if (finding.get("type") == FINDING_TYPE_GAP
                and FINDING_STATUS_MISSING in finding.get("summary", "").lower()
                and doc_stem in finding.get("pair", "")):
            stale.append(finding.get("pair", "unknown"))
    return stale


def _reviewed_stems(reviewed_keys: list[str]) -> set[str]:
    """Extract doc stems from reviewed keys (e.g. 'product_md' -> 'product')."""
    return {k.removesuffix("_md") for k in reviewed_keys}


def _pair_involves_reviewed(pair_key: str, stems: set[str]) -> bool:
    """Check if a pair key (e.g. 'product_tech') involves any reviewed doc stem.

    Uses '_' delimiter splitting to avoid false positives
    (e.g. stem 'product' won't match 'production_metrics').
    """
    pair_parts = set(pair_key.split("_"))
    return bool(pair_parts & stems)


def _aggregate_findings(pairs: dict) -> dict:
    """Sum conflicts/duplications/gaps across pairs and derive status."""
    total_conflicts = total_dups = total_gaps = 0
    for pair_data in pairs.values():
        total_conflicts += pair_data.get("conflicts", 0)
        total_dups += pair_data.get("duplications", 0)
        total_gaps += pair_data.get("gaps", 0)
    return {
        "status": DocStatus.NEEDS_WORK if (total_conflicts or total_dups or total_gaps) else DocStatus.PASS,
        "conflicts_found": total_conflicts,
        "duplications_found": total_dups,
        "gaps_found": total_gaps,
    }


def pair_has_content(pair: object) -> bool:
    """True if a cross-validation pair dict carries any conflict /
    duplication / gap count or at least one finding.

    Used by ``update-quality`` to decide whether the sub-agent actually
    emitted cross-doc observations worth preserving.
    """
    if not isinstance(pair, dict):
        return False
    if pair.get("findings"):
        return True
    return any(
        int(pair.get(k, 0) or 0) > 0
        for k in ("conflicts", "duplications", "gaps")
    )


def invalidate_stale_pairs(
    prior_cv: dict | None, reviewed_keys: list[str]
) -> dict | None:
    """Clear findings from prior cross-validation pairs that involve any reviewed doc.

    Returns a shallow-mutated copy of prior_cv, or None if prior_cv is None.
    """
    if not prior_cv or not reviewed_keys:
        return prior_cv
    pairs = prior_cv.get("pairs", {})
    if not pairs:
        return prior_cv

    stems = _reviewed_stems(reviewed_keys)
    result = {**prior_cv, "pairs": {}}

    for pair_key, pair_data in pairs.items():
        if _pair_involves_reviewed(pair_key, stems):
            result["pairs"][pair_key] = {
                **pair_data,
                "status": DocStatus.PASS,
                "conflicts": 0, "duplications": 0, "gaps": 0,
                "findings": [],
            }
        else:
            result["pairs"][pair_key] = pair_data

    non_stale = {k: v for k, v in result["pairs"].items()
                 if not _pair_involves_reviewed(k, stems)}
    agg = _aggregate_findings(non_stale)
    result.update(agg)
    result["findings"] = [
        f for f in prior_cv.get("findings", [])
        if not _pair_involves_reviewed(f.get("pair", ""), stems)
    ]
    return result


def _build_cross_validation(
    cv_input: dict | None,
    reviewed_keys: list[str],
    *,
    prior_advisories: list[dict] | None = None,
) -> dict | None:
    """Build the cross_validation block from AI-supplied pair data.

    Findings are intentionally stored in two places: once per-pair
    (for pair-scoped queries) and once in a top-level ``findings``
    array with an injected ``pair`` field (for flat iteration).
    Both must be kept in sync if the format changes.

    ``prior_advisories`` carries ``advisory_cross_validation`` findings
    surfaced by earlier per-doc reviews. They are merged into the
    matching pair so a final-scope reviewer inherits every prior
    advisory without having to re-detect the concern. Callers that
    don't care pass ``None``; :func:`collect_prior_advisories` is the
    standard producer.
    """
    if cv_input is None or len(reviewed_keys) < MIN_REVIEWED_KEYS_FOR_CV:
        return None
    pairs_input = cv_input.get("pairs", {})
    pairs_out: dict[str, dict] = {}
    for pair_key, pair_data in pairs_input.items():
        conflicts = pair_data.get("conflicts", 0)
        dups = pair_data.get("duplications", 0)
        gaps = pair_data.get("gaps", 0)
        pair_out: dict = {
            "status": DocStatus.NEEDS_WORK if _has_issues(pair_data) else DocStatus.PASS,
            "conflicts": conflicts,
            "duplications": dups,
            "gaps": gaps,
        }
        findings_input = pair_data.get("findings", [])
        validated = [f for f in findings_input if is_valid_finding(f)]
        if validated:
            pair_out["findings"] = validated
        pairs_out[pair_key] = pair_out

    if prior_advisories:
        _merge_prior_advisories(pairs_out, prior_advisories)

    agg = _aggregate_findings(pairs_out)
    result: dict = {
        **agg,
        "pairs_checked": len(pairs_out),
    }

    all_findings = []
    for pair_key, pair_out in pairs_out.items():
        for f in pair_out.get("findings", []):
            all_findings.append({"pair": pair_key, **f})
    if all_findings:
        result["findings"] = all_findings

    result["pairs"] = pairs_out
    return result


def _merge_prior_advisories(
    pairs_out: dict[str, dict], prior_advisories: list[dict],
) -> None:
    """Append advisories to their matching pair's ``findings`` list.

    Creates the pair row when the final-scope cv_input does not
    mention it; preserves existing findings and de-dupes by summary so
    re-running an identical final-scope assessment is idempotent.
    """
    for advisory in prior_advisories:
        if not isinstance(advisory, dict):
            continue
        if not is_valid_finding(advisory):
            continue
        pair_key = str(advisory.get("pair", ""))
        if not pair_key:
            continue
        pair = pairs_out.setdefault(pair_key, {
            "status": DocStatus.PASS,
            "conflicts": 0,
            "duplications": 0,
            "gaps": 0,
        })
        existing = pair.setdefault("findings", [])
        summary = str(
            advisory.get("summary") or advisory.get("description") or ""
        )
        already = any(
            isinstance(f, dict)
            and str(f.get("summary") or f.get("description") or "") == summary
            and f.get("type") == advisory.get("type")
            for f in existing
        )
        if already:
            continue
        merged = {k: v for k, v in advisory.items() if k != "pair"}
        existing.append(merged)
