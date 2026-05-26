#!/usr/bin/env python3
"""Build and update review-quality.json artifact from an AI assessment input.

Usage:
  review/update-quality.py --type <steering|spec|prd> --doc-dir <path>
      [--spec-name <name>] [--input <path>] [--output <path>]
      [--dry-run] [--validate-only]

--doc-dir        Directory that contains the documents being reviewed.
                 The script runs Tier 1 scripts against files here and writes
                 review-quality.json into this directory by default.
--input          Path to AI assessment JSON (lightweight input); defaults to stdin.
--output         Override the default output path (<doc-dir>/review-quality.json).
--dry-run        Assemble and print the artifact to stdout; do not write it.
--validate-only  Validate input JSON only; do not assemble or write the artifact.
                 Exits 0 with "OK" on success, exits 1 on validation failure.

Exit codes: 0 success, 1 validation/assembly failure, 2 write/file failure.
On success the absolute path of the written artifact is printed to stdout.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import json
import os
from pathlib import Path

from sdd_core.time import ts_now
from sdd_core.paths import (
    find_workflow_root, WORKFLOW_DIR, doc_dir_path,
    review_quality_artifact_path, spec_name_from_doc_path,
)
from review_quality.registry import DOCUMENT_REGISTRY, SCHEMA_VERSION, effective_doc_keys
from review_quality.io import load_input, write_artifact
from review_quality.validation import validate_input
from review_quality.tier1 import run_tier1_scripts
from review_quality.scoring import (
    derive_overall_score, derive_overall_status, derive_comprehension_fields,
    apply_cross_validation_cap, aggregate_facet_issues, count_cv_findings,
    doc_keys_for_scope,
)
from review_quality.builders import (
    merge_documents, build_history,
    _build_cross_validation, _check_spec_type, _default_comprehension,
    BuildContext, _CONTEXT_BUILDERS, _SUPPLEMENTAL_BUILDERS,
)
from review_quality.cross_validation import (
    collect_prior_advisories, invalidate_stale_pairs, pair_has_content,
)
from review_quality.staleness import compute_document_hashes
from review_quality.constants import (
    REVIEW_QUALITY_FILENAME, REVIEW_SCOPES,
    SCOPE_PER_DOCUMENT, SCOPE_FINAL,
)
from review_quality.facet_predicates import SpecMeta
from sdd_core import (
    cli, git as sdd_git, output, paths, preflight_state,
    review_quality_schema as rq_schema,
)
from sdd_core.specs import is_bug_fix_spec


# Review-type discriminator: only ``spec`` triggers spec-meta predicates and bug-fix branching.
REVIEW_TYPE_SPEC = "spec"
# Default spec_type when input omits it and the spec name does not parse as bug-fix.
SPEC_TYPE_STANDARD = "standard"
# spec_type that toggles bug-fix-specific facet predicates.
SPEC_TYPE_BUG_FIX = "bug-fix"
# Finding-source tag for per-doc facet rows lifted onto active.issues.
FINDING_SOURCE_FACET = "facet_issue"
# Finding-source tag for cross-doc rows lifted onto active.issues.
FINDING_SOURCE_CROSS_VALIDATION = "cross_validation"


def _assume_removals_when_uncertain(spec_workflow_root: str) -> bool:
    """True when the working tree shows deletions OR git is unreachable.

    Conservative default — used to evaluate ``additive_only_feature``
    for structural-na facet suppression. Predicates that consume this
    signal must treat ``True`` as "do not suppress" so an environmental
    failure (no git, detached worktree, timeout) keeps structural-na
    suppression off until we can prove the spec is additive-only.
    """
    repo_root = Path(spec_workflow_root).resolve().parent
    if not sdd_git.is_inside_work_tree(repo_root):
        return True
    rows = sdd_git.diff_name_status(cwd=repo_root)
    if rows is None:
        return True
    for status, _path in rows:
        if status.startswith(("D", "R")):
            return True
    return False


def _build_spec_meta(
    *, review_type: str, spec_name: str, input_data: dict,
    spec_workflow_root: str,
) -> SpecMeta | None:
    """Construct ``SpecMeta`` for predicate evaluation.

    A ``None`` return short-circuits the predicate evaluator
    (:func:`facet_predicates.evaluate` honours the ``meta is None``
    case), so non-spec review types preserve existing facet weights.
    """
    if review_type != REVIEW_TYPE_SPEC:
        return None
    spec_type = input_data.get("spec_type")
    if not spec_type:
        spec_type = SPEC_TYPE_BUG_FIX if is_bug_fix_spec(spec_name or "") else SPEC_TYPE_STANDARD
    return SpecMeta(
        spec_name=spec_name or "",
        spec_type=spec_type,
        review_type=review_type,
        has_removals=_assume_removals_when_uncertain(spec_workflow_root),
    )


def _count_pair_findings(pair_data: dict) -> int:
    """Count all findings in a single cross-validation pair, including nested findings arrays."""
    explicit = len(pair_data.get("findings", []))
    if explicit > 0:
        return explicit
    return pair_data.get("duplications", 0) + pair_data.get("conflicts", 0)


def _collect_input_finding_rows(input_data: dict) -> list[dict]:
    """Lift sub-agent-supplied per-finding rows into a flat list.

    Sub-agents may attach a ``findings: [...]`` array under each
    ``tier2_scores[doc_key][n]`` and under
    ``cross_validation.pairs[*]``. Each row carries ``severity``,
    ``summary``, and (for actionable rows) ``root_cause_kind``. When
    present, the rows are surfaced verbatim on ``active.issues`` so the
    post-review aggregator can branch on the kind enum without
    re-deriving it from facet counts. Returns ``[]`` when the sub-agent
    only emitted the legacy counts shape.
    """
    out: list[dict] = []
    tier2 = input_data.get("tier2_scores")
    if isinstance(tier2, dict):
        for doc_key, entries in tier2.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                facet_id = str(entry.get("id") or "")
                rows = entry.get("findings")
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    record = dict(row)
                    record.setdefault("source", FINDING_SOURCE_FACET)
                    record.setdefault("doc_key", doc_key)
                    if facet_id:
                        record.setdefault("facet_id", facet_id)
                    out.append(record)
    cv = input_data.get("cross_validation")
    if isinstance(cv, dict):
        from review_quality.registry_helpers import is_valid_finding
        pairs = cv.get("pairs") or {}
        for pair_key, pair_data in pairs.items():
            if not isinstance(pair_data, dict):
                continue
            rows = pair_data.get("findings")
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                # Malformed cv findings (unknown type / empty summary)
                # are stripped from the artifact by the builder; skip
                # them here so the lifted ``active.issues`` view stays
                # in sync with what actually persists.
                if not is_valid_finding(row):
                    continue
                record = dict(row)
                record.setdefault("source", FINDING_SOURCE_CROSS_VALIDATION)
                record.setdefault("pair", pair_key)
                # Map ``type`` (cross-validation vocab) onto severity so
                # the aggregator's actionable-severity check is uniform
                # across facet and cross-doc findings.
                if "severity" not in record and "type" in record:
                    record["severity"] = record["type"]
                out.append(record)
    return out


def validate_findings_consistency(assessment_input: dict, built_artifact: dict) -> list[str]:
    """Warn if cross-validation counts in input don't match artifact findings."""
    warnings: list[str] = []
    cv_input = assessment_input.get("cross_validation", {})
    if not isinstance(cv_input, dict):
        return warnings
    pairs_input = cv_input.get("pairs", {})
    artifact_cv = built_artifact.get("cross_validation") or {}
    artifact_pairs = artifact_cv.get("pairs", {})
    for pair_key, pair_data in pairs_input.items():
        if not isinstance(pair_data, dict):
            continue
        input_count = _count_pair_findings(pair_data)
        artifact_pair = artifact_pairs.get(pair_key, {})
        artifact_count = len(artifact_pair.get("findings", []))
        if input_count > 0 and artifact_count == 0:
            warnings.append(
                f"{pair_key}: assessment reports {input_count} issue(s) "
                f"but findings array is empty — possible data loss"
            )
    return warnings


def build_artifact(
    input_data: dict,
    doc_dir: str,
    review_type: str,
    spec_name: str,
    prior: dict | None,
    spec_workflow_root: str,
    *,
    scope: str | None = None,
) -> dict:
    """Assemble the complete artifact from AI input, Tier 1 results, and prior.

    *scope* (``per-document`` | ``final`` | ``None``) selects which doc
    keys drive ``overall_status``. ``per-document`` derives status only
    from docs actually reviewed in this gate; ``final`` (default) checks
    every expected doc — future-doc absence becomes ``INCOMPLETE``.
    """
    reg = DOCUMENT_REGISTRY[review_type]
    now = ts_now()

    if review_type == REVIEW_TYPE_SPEC and spec_name:
        _check_spec_type(spec_name, input_data.get("spec_type", SPEC_TYPE_STANDARD))

    reviewed_keys_raw = input_data.get("documents_reviewed", [])
    reviewed_keys_for_tier1 = [k for k in reviewed_keys_raw if k in reg["doc_keys"]]

    tier1_results = run_tier1_scripts(
        doc_dir, review_type, reviewed_keys_for_tier1, spec_workflow_root,
    )

    spec_meta = _build_spec_meta(
        review_type=review_type,
        spec_name=spec_name,
        input_data=input_data,
        spec_workflow_root=spec_workflow_root,
    )
    documents, reviewed_keys = merge_documents(
        input_data, tier1_results, prior, review_type, now,
        spec_meta=spec_meta,
    )

    active_keys = effective_doc_keys(review_type, set(documents))
    status_keys = doc_keys_for_scope(scope, active_keys, reviewed_keys)
    cv_input_for_status = input_data.get("cross_validation")
    cv_for_status = _build_cross_validation(cv_input_for_status, reviewed_keys) if cv_input_for_status else None
    overall_status = derive_overall_status(
        documents, status_keys,
        artifact={"documents": documents, "cross_validation": cv_for_status},
    )
    score_band = overall_status.split("_WITH_")[0]
    overall_score = derive_overall_score(documents, active_keys, score_band)

    all_reviewed = set(reviewed_keys) == set(reg["doc_keys"])
    if all_reviewed:
        last_full_review_at = now
    else:
        last_full_review_at = (prior or {}).get("last_full_review_at") if prior else None

    cv_input = input_data.get("cross_validation")
    # On a final-scope review, inherit ``advisory_cross_validation``
    # findings from prior per-doc reviews so the reviewer doesn't need
    # to re-detect cross-doc concerns. Merge only fires at final scope.
    prior_advisories: list[dict] = (
        collect_prior_advisories((prior or {}).get("cross_validation"))
        if all_reviewed else []
    )
    cross_validation = _build_cross_validation(
        cv_input, reviewed_keys, prior_advisories=prior_advisories,
    )
    if cross_validation is None and prior:
        cross_validation = invalidate_stale_pairs(
            prior.get("cross_validation"), reviewed_keys
        )

    overall_score, cv_deduction = apply_cross_validation_cap(
        overall_score, cross_validation,
    )

    doc_filenames_for_hash = [
        reg["doc_files"][k] for k in documents if k in reg["doc_files"]
    ]
    finding_rows = _collect_input_finding_rows(input_data)
    # Sub-agents that surface explicit per-finding rows replace the
    # legacy counts dict on ``issues``; the list shape carries
    # ``root_cause_kind`` for the post-review aggregator. When the
    # sub-agent only emitted counts, the historical dict shape stays in
    # place so legacy artifacts and fixtures keep validating.
    issues_payload: list | dict = (
        finding_rows if finding_rows else aggregate_facet_issues(documents)
    )
    # Lift the sub-agent's per-doc demotion predictions onto the active
    # snapshot so the final-scope reviewer reads them up front. Empty
    # when the input omits the field or no demotions were flagged.
    demotions_input = input_data.get("final_scope_demotions_predicted")
    final_scope_demotions_predicted: list[dict] = []
    if isinstance(demotions_input, list):
        for row in demotions_input:
            if isinstance(row, dict):
                final_scope_demotions_predicted.append(dict(row))

    # Replay the publish side: the launch envelope that drove this
    # review carried ``tier2_facet_criteria_by_scope`` for facets whose
    # criteria differ across scopes. The sub-agent echoes the field so
    # the artifact captures both the criteria the review consulted and
    # any predicted demotions in one place.
    facet_criteria_by_scope_input = input_data.get(
        "tier2_facet_criteria_by_scope",
    )
    facet_criteria_by_scope: dict = {}
    if isinstance(facet_criteria_by_scope_input, dict):
        facet_criteria_by_scope = dict(facet_criteria_by_scope_input)

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "review_type": review_type,
        "generated_at": now,
        "last_full_review_at": last_full_review_at,
        "skill": reg["skill_name"],
        "skill_version": input_data.get("skill_version", ""),
        "overall_status": overall_status,
        "overall_score": overall_score,
        "issues": issues_payload,
        "documents": documents,
        "document_hashes": compute_document_hashes(doc_dir, doc_filenames_for_hash),
        "cross_validation": cross_validation,
        "final_scope_demotions_predicted": final_scope_demotions_predicted,
        "tier2_facet_criteria_by_scope": facet_criteria_by_scope,
    }
    if isinstance(issues_payload, dict):
        artifact["issue_counts"] = issues_payload
    else:
        artifact["issue_counts"] = aggregate_facet_issues(documents)
    if cv_deduction > 0:
        artifact["cross_validation_deduction"] = cv_deduction

    comp_field = reg["comprehension_field"]
    comp_input = input_data.get(comp_field) or {}
    artifact["comprehension"] = (
        derive_comprehension_fields(comp_input, all_reviewed)
        if comp_input
        else _default_comprehension()
    )

    ctx = BuildContext(
        review_type=review_type,
        spec_name=spec_name,
        prior=prior,
        all_reviewed=all_reviewed,
    )
    artifact["context"] = _CONTEXT_BUILDERS[review_type](input_data, ctx)
    artifact["supplemental"] = _SUPPLEMENTAL_BUILDERS[review_type](input_data, ctx)

    if scope:
        artifact["scope"] = scope

    artifact["history"] = build_history(artifact, prior, review_type)

    return artifact


def _load_canonical_doc(path: str) -> dict:
    """Read the existing artifact and return a v3-shaped dict.

    Pre-v3 artifacts (semver string ``schema_version``) flow through the
    legacy migration registry first so v1 ``history.{first,previous}``
    upgrades to ``history.runs`` before the canonicalisation step lifts
    that list into the v3 ``history`` array. Already-canonical v3
    artifacts (integer ``schema_version``) skip the legacy registry —
    the int marker is the canonicalisation signal.
    """
    if not os.path.isfile(path):
        return rq_schema.load(path)
    raw = output.safe_read_json(path)
    if not isinstance(raw, dict):
        return rq_schema.load(path)
    if isinstance(raw.get("schema_version"), int):
        return rq_schema.upgrade_if_needed(raw)
    try:
        from migrations import migrate as _legacy_migrate
        import migrations.review_quality  # noqa: F401 — registers steps
        upgraded = _legacy_migrate(raw, "3.0.0")
    except Exception:
        upgraded = raw
    return rq_schema.upgrade_if_needed(upgraded)


def _resolve_prior_active(canonical_doc: dict) -> dict | None:
    """Return the prior ``active`` snapshot, ``None`` when no prior exists.

    Bridges the v3 ``history`` (list of prior actives) and the legacy
    ``history.runs`` shape that :func:`build_history` walks. Prefers
    ``active.history.runs`` when present so unbroken streaks survive
    untouched; otherwise reconstructs ``runs`` from the v3 history list
    so freshly-reshaped artifacts retain their accumulated runs.
    """
    active = rq_schema.get_active(canonical_doc)
    if not active:
        return None
    prior = dict(active)
    history_block = prior.get("history")
    if isinstance(history_block, dict) and isinstance(
        history_block.get("runs"), list
    ):
        return prior
    v3_history = canonical_doc.get("history")
    if isinstance(v3_history, list) and v3_history:
        prior["history"] = {
            "runs": [dict(r) for r in v3_history if isinstance(r, dict)],
        }
    return prior


def _validate_existing_artifact_compat(path: str) -> None:
    """Surface schema-major / clock-skew issues against the prior artifact.

    The canonical schema loader silently absorbs legacy shapes via
    :func:`upgrade_if_needed`. Two compatibility signals predate the
    upgrader and stay user-facing here: a future-major schema must not
    silently downgrade, and a clock-skew ``generated_at`` must remain a
    visible warning so ops can spot the drift before it cascades.
    """
    if not os.path.isfile(path):
        return
    try:
        existing = output.safe_read_json(path)
    except ValueError as exc:
        output.warn(
            f"could not read existing artifact at {path!r}: {exc}"
        )
        return
    if not isinstance(existing, dict):
        return

    raw_version = existing.get("schema_version")
    if isinstance(raw_version, str):
        version_str = raw_version
    elif isinstance(raw_version, (int, float)):
        version_str = str(raw_version)
    else:
        version_str = "1.0.0"
    try:
        ex_major = int(version_str.split(".")[0])
    except (ValueError, IndexError):
        ex_major = 0
    if ex_major > rq_schema.SCHEMA_VERSION:
        output.error(
            f"Existing artifact has incompatible schema_version "
            f"{version_str!r} (script supports {rq_schema.SCHEMA_VERSION})"
        )

    gen_at = existing.get("generated_at") or (
        existing.get("active") or {}
    ).get("generated_at") or ""
    if gen_at:
        try:
            from datetime import datetime, timezone
            artifact_dt = datetime.fromisoformat(
                str(gen_at).replace("Z", "+00:00")
            )
            if artifact_dt > datetime.now(timezone.utc):
                output.warn(
                    f"clock skew detected — existing artifact generated_at"
                    f" {gen_at!r} is in the future"
                )
        except ValueError:
            pass


def _route_artifact_into_v3(
    canonical_doc: dict,
    new_active: dict,
    *,
    scope: str | None,
    doc_key: str | None,
    review_type: str,
    documents_reviewed: list,
    prior_active: dict | None,
) -> dict:
    """Route the freshly-built ``new_active`` snapshot into the v3 envelope.

    Scope rules:
      * ``per-document`` updates only ``by_scope.per-document.<doc_key>``;
        ``active`` is touched only when the existing gate scope is also
        ``per-document``. The slot list defaults to *documents_reviewed*
        when *doc_key* is omitted so single-call multi-doc per-doc reviews
        still land in the right slots.
      * ``final`` updates ``active`` AND ``by_scope.final``; the prior
        ``active`` is appended to the cap-10 ``history`` list before the
        replacement lands.
      * Unspecified scope behaves as ``final`` (today's default).
    """
    if not canonical_doc.get("review_type"):
        canonical_doc["review_type"] = review_type

    per_document = scope == SCOPE_PER_DOCUMENT
    final_scope = scope is None or scope == SCOPE_FINAL

    if per_document:
        slots: list[str] = []
        if doc_key:
            slots = [doc_key]
        else:
            # Drop the new_active body into one slot per reviewed doc so
            # the per-document view aggregates without forcing the agent
            # to invoke update-quality.py once per doc.
            slots = [k for k in documents_reviewed if isinstance(k, str)]
        for slot in slots:
            rq_schema.set_by_scope(
                canonical_doc, SCOPE_PER_DOCUMENT, slot, new_active,
            )
        prior_scope = (prior_active or {}).get("scope")
        if prior_scope == SCOPE_PER_DOCUMENT:
            rq_schema.set_active(canonical_doc, new_active)
        return canonical_doc

    if final_scope:
        if prior_active:
            rq_schema.append_history(canonical_doc, prior_active)
        rq_schema.set_active(canonical_doc, new_active)
        rq_schema.set_by_scope(canonical_doc, SCOPE_FINAL, None, new_active)
        return canonical_doc

    # Unknown scope falls through as final-shaped to keep the path total.
    rq_schema.set_active(canonical_doc, new_active)
    rq_schema.set_by_scope(canonical_doc, SCOPE_FINAL, None, new_active)
    return canonical_doc


def _build_parser():
    """Construct the argparse parser for ``review/update-quality.py``.

    Extracted so the builder unit-tests (``tests/test_command_templates``)
    can round-trip rendered commands through the script's own argparse
    contract without invoking ``main()``.
    """
    parser = cli.strict_parser(
        description="Build and update review-quality.json artifact from an AI assessment input"
    )
    parser.add_argument("--type", required=True, dest="review_type",
                        choices=list(DOCUMENT_REGISTRY), help="Review type")
    parser.add_argument("--doc-dir", help=(
        "Directory containing documents being reviewed"
    ))
    # Canonical review-locator vocabulary: --category / --target-name
    # (aliased --spec-name). When both --category and --target-name are
    # provided, the script resolves --doc-dir from them so callers can
    # use the same vocabulary as pipeline-tick.py / count-effective-lines.py.
    cli.add_document_selectors(
        parser, spec_name=True, category=True,
        # --target-name is resolved on the unified helper; we keep the
        # original --spec-name alias as the canonical dest.
    )
    parser.add_argument("--input", dest="input_path", help="Path to AI assessment JSON (default: stdin)")
    parser.add_argument("--output", dest="output_path", help="Override output path")
    parser.add_argument("--dry-run", action="store_true", help="Print artifact without writing")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate input JSON only; do not assemble or write")
    parser.add_argument(
        "--scope", default=None, choices=REVIEW_SCOPES,
        help=(
            "Review scope. 'per-document' derives overall_status only "
            "from docs reviewed in this gate; 'final' (default) checks "
            "every expected doc."
        ),
    )
    # ``--doc-key`` (not ``--doc``) — the locator vocabulary reserves
    # ``--doc`` for filenames (e.g. ``requirements.md``). This flag
    # carries an internal *doc key* (e.g. ``requirements_md``), so
    # using a distinct name keeps the shared selector helper
    # single-authority.
    parser.add_argument(
        "--doc-key", dest="doc_key", default=None,
        help=(
            "Per-document scope target — explicit doc key (e.g. "
            "requirements_md). When omitted under --scope per-document, "
            "the slots derive from documents_reviewed in the input."
        ),
    )
    return parser


def main() -> None:

    parser = _build_parser()
    # Lens 5: argparse usage errors (missing required args) are
    # recoverable — surface as ``preflight_required`` so the gate
    # routes the operator back through ``ensure-healthy.py`` (which
    # re-runs ``build_review_update_quality_command`` with the right
    # ``--type`` flag) rather than failing with exit 2.
    import sys as _sys
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        if exc.code == 2:
            from sdd_core.command_templates import build_ensure_healthy_command
            output.preflight_required(
                {
                    "reason": "missing-required-arg",
                    "argv": _sys.argv[1:],
                },
                "review/update-quality.py invoked without all required args",
                hint=(
                    "The canonical caller is workspace/ensure-healthy.py, "
                    "which routes through build_review_update_quality_command. "
                    "Re-run the emitter rather than synthesising flags."
                ),
                next_action_command=build_ensure_healthy_command(),
                error="missing-required-arg",
            )
        raise

    review_type = args.review_type
    doc_dir = args.doc_dir
    spec_name = args.spec_name
    category = getattr(args, "category", None)
    input_path = args.input_path
    output_path = args.output_path
    dry_run = args.dry_run
    validate_only = args.validate_only

    if not doc_dir and category and spec_name and not validate_only:
        project_root = paths.resolve_project_path(args)
        doc_dir = doc_dir_path(category, spec_name, project_root)

    if not doc_dir and not validate_only:
        parser.error("--doc-dir (or --category + --target-name) is required")
    if review_type == REVIEW_TYPE_SPEC:
        if not spec_name and not validate_only:
            parser.error("--spec-name is required when --type spec")
        if spec_name and (".." in spec_name or os.path.isabs(spec_name)):
            parser.error(f"path traversal detected in --spec-name: {spec_name!r}")

    input_data = load_input(input_path)
    validation_errors = validate_input(input_data, review_type)
    if validation_errors:
        output.error("; ".join(validation_errors))

    if validate_only:
        output.success({"result": "valid"}, "Input JSON is valid")

    try:
        project_root = find_workflow_root(doc_dir, resolve_symlinks=False)
        project_root_path = str(project_root)
        spec_workflow_root = os.path.join(str(project_root), WORKFLOW_DIR)
    except FileNotFoundError:
        project_root_path = os.path.dirname(os.path.abspath(doc_dir))
        spec_workflow_root = os.path.dirname(os.path.abspath(doc_dir))

    if output_path is None:
        # Resolve via the canonical single-source helper so the path
        # stays invariant across scopes — only the in-artifact schema
        # absorbs the scope dimension.
        if review_type == REVIEW_TYPE_SPEC and spec_name:
            output_path = str(
                Path(project_root_path) / review_quality_artifact_path(spec_name)
            )
        else:
            output_path = os.path.join(
                os.path.abspath(doc_dir), REVIEW_QUALITY_FILENAME,
            )

    _validate_existing_artifact_compat(output_path)
    canonical_doc = _load_canonical_doc(output_path)
    prior_active = _resolve_prior_active(canonical_doc)
    artifact = build_artifact(
        input_data, doc_dir, review_type, spec_name, prior_active,
        spec_workflow_root, scope=args.scope,
    )

    consistency_warnings = validate_findings_consistency(input_data, artifact)

    cv_input = input_data.get("cross_validation")
    has_real_pair_data = (
        isinstance(cv_input, dict)
        and any(pair_has_content(v) for v in (cv_input.get("pairs") or {}).values())
    )
    artifact_cv = artifact.get("cross_validation")
    if has_real_pair_data and artifact_cv is None:
        # Hard error: the assessment emitted cross-doc findings but they
        # never made it onto the artifact (typical cause: single-doc
        # review whose MIN_REVIEWED_KEYS guard dropped the block). Silent
        # ``null`` is worse than a retry because consumers can't tell the
        # AI "forgot" from "had nothing to say".
        output.error(
            "cross-validation findings dropped during artifact assembly",
            next_action_command="--phase launch (retry with --review-scope full or add the referenced doc to documents_reviewed)",
            context=json.dumps({
                "input_pair_keys": sorted(cv_input.get("pairs", {}).keys()),
                "reviewed_keys": list(input_data.get("documents_reviewed", [])),
                "dropped": consistency_warnings,
            }),
        )

    canonical_doc = _route_artifact_into_v3(
        canonical_doc, artifact,
        scope=args.scope, doc_key=args.doc_key,
        review_type=review_type,
        documents_reviewed=list(input_data.get("documents_reviewed") or []),
        prior_active=prior_active,
    )

    schema_errors = rq_schema.validate_v3(canonical_doc)
    if schema_errors:
        # Surface all schema errors at once so the sub-agent can repair
        # the entire batch in a single retry.
        output.error("; ".join(schema_errors))

    if dry_run:
        result = dict(canonical_doc)
        if consistency_warnings:
            result["consistency_warnings"] = consistency_warnings
        output.success(result, f"[dry-run] Would write to: {output_path}")

    try:
        rq_schema.atomic_write(output_path, canonical_doc)
    except OSError as exc:
        output.error(
            f"failed to write artifact to {output_path!r}: {exc}",
            exit_code=2,
        )

    preflight_state.mark_resolved(
        "review_quality_stale", workspace=project_root_path,
    )
    result_data = {"path": output_path}
    if consistency_warnings:
        result_data["consistency_warnings"] = consistency_warnings
    output.success(result_data, f"Quality artifact written to {output_path}")


if __name__ == "__main__":
    cli.run_main(main)
