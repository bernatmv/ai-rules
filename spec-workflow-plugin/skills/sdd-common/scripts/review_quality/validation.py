"""Input validation logic for review quality artifacts."""
from __future__ import annotations

from sdd_core import output
from sdd_core.review_input import (
    INPUT_KEY_CROSS_VALIDATION,
    INPUT_KEY_DOCUMENTS_REVIEWED,
    INPUT_KEY_SKILL_VERSION,
    INPUT_KEY_TESTING_THOROUGHNESS,
    INPUT_KEY_TIER2_SCORES,
)
from sdd_core.review_quality_schema import ROOT_CAUSE_KINDS

from .registry import (
    DOCUMENT_REGISTRY,
    SEMVER_RE,
    SCORE_VALUE_MAP,
    VALID_SPEC_TYPES,
    VALID_FINDING_TYPES,
    VALID_THOROUGHNESS_RATINGS,
    is_valid_finding,
    tier1_facets_for_type,
    all_doc_keys_for_type,
)


def _validate_finding_kinds(entry: dict, doc_key: str, facet_id: str) -> list[str]:
    """Verify ``root_cause_kind`` on each finding under a tier2 entry.

    Sub-agents may surface explicit per-finding rows under
    ``tier2_scores[doc_key][n].findings[]``; when present, every entry
    carrying an actionable severity must declare ``root_cause_kind``
    from the canonical enum. Counts-only entries (no ``findings`` array)
    are passed through — the legacy shape stays valid so existing
    fixtures need no migration.
    """
    errors: list[str] = []
    findings = entry.get("findings")
    if findings is None:
        return errors
    if not isinstance(findings, list):
        errors.append(
            f"facet {facet_id!r} in {doc_key} 'findings' must be a list; "
            f"got {type(findings).__name__}"
        )
        return errors
    legal = sorted(ROOT_CAUSE_KINDS)
    actionable = {"critical", "warning", "fail", "conflict"}
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(
                f"facet {facet_id!r} in {doc_key} findings[{idx}] must be a "
                f"dict; got {type(finding).__name__}"
            )
            continue
        severity = str(finding.get("severity") or "").lower()
        if severity not in actionable:
            continue
        kind = finding.get("root_cause_kind")
        if kind is None:
            errors.append(
                f"facet {facet_id!r} in {doc_key} findings[{idx}] is missing "
                f"required 'root_cause_kind' (severity={severity!r}); "
                f"expected one of {legal}"
            )
            continue
        if not isinstance(kind, str) or kind not in ROOT_CAUSE_KINDS:
            errors.append(
                f"facet {facet_id!r} in {doc_key} findings[{idx}] "
                f"root_cause_kind={kind!r} is not one of {legal}"
            )
    return errors
from .registry_helpers import (
    canonical_cross_validation_keys,
    cross_validation_pairs_for_type,
)


def _cross_validation_pair_key_index(review_type: str) -> tuple[set[str], dict[str, str]]:
    """Return ``(canonical_keys, stem_to_canonical)`` for *review_type*.

    Canonical shape is ``<doc_a>_x_<doc_b>`` where ``doc_a`` / ``doc_b``
    are full :data:`DOCUMENT_REGISTRY` doc_keys (e.g.
    ``product_md_x_tech_md``). The sole alternative form is the bare
    stem ``<stem_a>_<stem_b>`` used by a handful of legacy test
    fixtures; it is passed through untouched so downstream consumers
    that already key on stems keep working.

    The double-underscore form has no legitimate producer and is not
    accepted — the agent-facing reference docs now quote the canonical
    list emitted by ``review_quality/print-pair-keys.py`` so drift is
    structurally impossible.
    """
    pairs = cross_validation_pairs_for_type(review_type)
    canonical = canonical_cross_validation_keys(review_type)
    stem_form: dict[str, str] = {}
    for (a, b) in pairs:
        forward = f"{a}_x_{b}"
        a_stem = a.removesuffix("_md")
        b_stem = b.removesuffix("_md")
        stem_form[f"{a_stem}_{b_stem}"] = forward
        stem_form[f"{b_stem}_{a_stem}"] = forward
    return canonical, stem_form


def _validate_schema(raw_input: dict, review_type: str) -> list[str]:
    """Check required fields and semver format."""
    errors: list[str] = []
    required_fields = (
        INPUT_KEY_SKILL_VERSION,
        INPUT_KEY_DOCUMENTS_REVIEWED,
        INPUT_KEY_TIER2_SCORES,
    )
    for field in required_fields:
        if field not in raw_input:
            errors.append(f"Missing required field: {field}")
    if errors:
        return errors
    if not SEMVER_RE.match(str(raw_input.get(INPUT_KEY_SKILL_VERSION, ""))):
        errors.append(
            f"skill_version must be semver (x.y.z): {raw_input[INPUT_KEY_SKILL_VERSION]!r}"
        )
    if review_type == "spec":
        if "spec_type" not in raw_input:
            errors.append("Missing required field for spec: spec_type")
        elif raw_input.get("spec_type") not in VALID_SPEC_TYPES:
            errors.append(
                f"spec_type must be one of {sorted(VALID_SPEC_TYPES)}, got: {raw_input['spec_type']!r}"
            )
    return errors


def _validate_tier2(raw_input: dict, review_type: str) -> tuple[list[str], list[str], int, int]:
    """Validate tier2_scores entries. Returns (errors, recognized_reviewed, supplied, accepted).

    ``score: "na"`` is only valid when accompanied by a non-empty
    ``na_justification`` — otherwise sub-agents could silently drop
    difficult facets and inflate the percent by shrinking the
    denominator. Coverage gaps (expected facets missing from the
    submitted input) surface as a ``tier2_coverage_incomplete`` warning
    so reviewers can see them without hard-blocking the artifact write.
    """
    errors: list[str] = []
    doc_registry = DOCUMENT_REGISTRY[review_type]
    known_doc_keys = all_doc_keys_for_type(review_type)

    recognized_reviewed = []
    for doc_key in list(raw_input.get(INPUT_KEY_DOCUMENTS_REVIEWED, [])):
        if doc_key not in known_doc_keys:
            output.warn(
                f"unknown document key in {INPUT_KEY_DOCUMENTS_REVIEWED}: {doc_key!r} — skipping"
            )
        else:
            recognized_reviewed.append(doc_key)

    tier1_ids = tier1_facets_for_type(review_type)
    valid_scores = set(SCORE_VALUE_MAP.keys())
    tier2_supplied = 0
    tier2_accepted = 0
    tier2_scores_in = raw_input.get(INPUT_KEY_TIER2_SCORES, {}) or {}
    seen_facets_by_doc: dict[str, set[str]] = {}
    for doc_key, entries in tier2_scores_in.items():
        if doc_key not in known_doc_keys:
            output.warn(
                f"unknown doc key in tier2_scores: {doc_key!r} — skipping"
            )
            continue
        known_facet_ids = {f["id"] for f in doc_registry["facets"].get(doc_key, [])}
        seen_facets = seen_facets_by_doc.setdefault(doc_key, set())
        for entry in (entries or []):
            facet_id = entry.get("id", "")
            tier2_supplied += 1
            if facet_id in tier1_ids:
                errors.append(
                    f"Tier 1 facet '{facet_id}' must not appear in tier2_scores"
                    " — script determines this score"
                )
            if facet_id not in known_facet_ids:
                output.warn(
                    f"unknown facet ID in tier2_scores[{doc_key!r}]: {facet_id!r} — skipping"
                )
                continue
            tier2_accepted += 1
            seen_facets.add(facet_id)
            score_value = entry.get("score")
            if score_value not in valid_scores:
                errors.append(
                    f"Invalid score value {score_value!r} for facet {facet_id!r}"
                    f" in {doc_key}. Must be one of: {sorted(valid_scores)}"
                )
            # Bare ``na`` is no longer accepted — require either a
            # concrete score or an explicit justification string.
            if score_value == "na":
                justification = entry.get("na_justification")
                if not (
                    isinstance(justification, str) and justification.strip()
                ):
                    errors.append(
                        f"facet {facet_id!r} in {doc_key} scored 'na' without "
                        "`na_justification`. Provide a non-empty justification "
                        "string explaining why the facet cannot be scored "
                        "(counts as a fail toward the denominator)."
                    )
            issues = entry.get("issues", {})
            if not isinstance(issues, dict) or not all(
                k in issues for k in ("critical", "warning", "suggestion")
            ):
                errors.append(
                    f"facet {facet_id!r} issues must have keys: critical, warning, suggestion"
                )
            else:
                for sev in ("critical", "warning", "suggestion"):
                    val = issues.get(sev)
                    if val is not None and not isinstance(val, int):
                        errors.append(
                            f"facet {facet_id!r} issues.{sev} must be int, "
                            f"got {type(val).__name__}"
                        )
            errors.extend(_validate_finding_kinds(entry, doc_key, facet_id))

    # Warn for tier2 facets expected by the registry but missing
    # from the submitted assessment — the denominator is otherwise
    # silently reduced and two specs reporting "100%" might have
    # reviewed different subsets.
    for doc_key in recognized_reviewed:
        known_facet_ids = {f["id"] for f in doc_registry["facets"].get(doc_key, [])}
        expected_tier2 = known_facet_ids - set(tier1_ids)
        seen = seen_facets_by_doc.get(doc_key, set())
        missing = sorted(expected_tier2 - seen)
        if missing:
            output.warn(
                f"tier2_coverage_incomplete[{doc_key!r}] — missing facets: "
                f"{missing}. Denominator may shrink; add entries or mark "
                f"them as 'na' with na_justification."
            )

    if recognized_reviewed and tier2_supplied > 0 and tier2_accepted == 0:
        errors.append(
            f"Accepted 0/{tier2_supplied} tier2 facet scores — all facet IDs"
            " were unrecognized. Check IDs against the registry."
        )
    if tier2_supplied > 0:
        output.info(
            f"Accepted {tier2_accepted}/{tier2_supplied} tier2 facet scores"
        )

    return errors, recognized_reviewed, tier2_supplied, tier2_accepted


def _validate_testing(raw_input: dict, review_type: str) -> list[str]:
    """Validate cross_validation pair keys and testing_thoroughness shape.

    Returns a list of blocking error messages (empty = valid). Shape
    warnings for individual findings remain non-blocking — stripping an
    unrecognised finding type is still a soft contract.

    Pair-key shape is validated against
    :func:`_cross_validation_pair_key_index` for *review_type*. Unknown
    keys that don't match the canonical or stem form are a hard error
    so data loss (finding attached to an unparseable pair key) cannot
    go unnoticed. The error envelope points recovery at
    ``review_quality/print-pair-keys.py`` — the single source of truth
    for the canonical set.
    """
    errors: list[str] = []
    cv = raw_input.get(INPUT_KEY_CROSS_VALIDATION, {})
    if isinstance(cv, dict) and cv.get("pairs"):
        canonical, stem_form = _cross_validation_pair_key_index(review_type)
        pairs_map = cv.get("pairs") or {}
        for pair_key in list(pairs_map.keys()):
            if pair_key in canonical:
                continue
            if pair_key in stem_form:
                # Bare-stem form is accepted verbatim so downstream
                # consumers that key on the stem form keep working.
                continue
            canonical_sample = sorted(canonical)[:3]
            errors.append(
                f"invalid cross_validation pair key {pair_key!r} for "
                f"review_type={review_type!r}; expected one of "
                f"{canonical_sample}\u2026 — run "
                f"`.spec-workflow/sdd review_quality/print-pair-keys.py "
                f"--type {review_type}` for the full canonical set"
            )

    if isinstance(cv, dict):
        legal_kinds = sorted(ROOT_CAUSE_KINDS)
        for pair_key, pair_data in cv.get("pairs", {}).items():
            if isinstance(pair_data, dict):
                for idx, f in enumerate(pair_data.get("findings", []) or []):
                    if not is_valid_finding(f):
                        if f.get("type") not in VALID_FINDING_TYPES:
                            output.warn(
                                f"unknown finding type {f.get('type')!r} in {pair_key}"
                            )
                        else:
                            output.warn(
                                f"finding in {pair_key} has empty/missing summary — will be stripped"
                            )
                        # Malformed findings are stripped by the artifact
                        # builder; skip kind enforcement so a single
                        # bad-shape finding doesn't double-error.
                        continue
                    ftype = str(f.get("type") or "").lower()
                    # ``conflict`` cross-validation findings drive the fix
                    # loop the same way actionable facet issues do — require
                    # the kind enum on those rows. Other types (duplication,
                    # gap, drift, advisory_cross_validation) stay optional.
                    if ftype != "conflict":
                        continue
                    kind = f.get("root_cause_kind")
                    if kind is None:
                        errors.append(
                            f"cross_validation pair {pair_key!r} findings[{idx}] "
                            f"is missing required 'root_cause_kind' "
                            f"(type='conflict'); expected one of {legal_kinds}"
                        )
                        continue
                    if not isinstance(kind, str) or kind not in ROOT_CAUSE_KINDS:
                        errors.append(
                            f"cross_validation pair {pair_key!r} findings[{idx}] "
                            f"root_cause_kind={kind!r} is not one of {legal_kinds}"
                        )

    tt = raw_input.get(INPUT_KEY_TESTING_THOROUGHNESS)
    if isinstance(tt, dict):
        if tt.get("rating") not in VALID_THOROUGHNESS_RATINGS:
            output.warn(
                f"testing_thoroughness.rating {tt.get('rating')!r} not in {sorted(VALID_THOROUGHNESS_RATINGS)}"
            )
        for item in tt.get("summary", []):
            if not isinstance(item, str):
                output.warn(
                    "testing_thoroughness.summary items must be strings — non-strings will be stripped"
                )
    elif isinstance(tt, str):
        if tt not in VALID_THOROUGHNESS_RATINGS:
            output.warn(
                f"testing_thoroughness {tt!r} not in {sorted(VALID_THOROUGHNESS_RATINGS)}"
            )

    return errors


def validate_input(raw_input: dict, review_type: str) -> list[str]:
    """Validate AI assessment input. Return list of error messages (empty = valid)."""
    errors = _validate_schema(raw_input, review_type)
    if errors:
        return errors

    tier2_errors, _recognized, _supplied, _accepted = _validate_tier2(raw_input, review_type)
    errors.extend(tier2_errors)

    testing_errors = _validate_testing(raw_input, review_type)
    errors.extend(testing_errors)

    return errors
