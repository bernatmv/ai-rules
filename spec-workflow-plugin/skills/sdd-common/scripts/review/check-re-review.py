#!/usr/bin/env python3
"""Check whether a document requires re-review before approval.

Stateless validation: reads the document's mtime and the existing
review-quality.json artifact to determine if a re-review is needed.

Usage:
    check-re-review.py --doc <filename> --spec-name <name>
        [--category spec|steering|discovery] [--workspace PATH]

Exit code: 0 always (result in JSON envelope).  The caller inspects
``data.re_review_required`` to decide whether to block approval.
"""
import _bootstrap  # noqa: F401

import os

from sdd_core import cli, output, paths
from sdd_core.paths import doc_dir_path
from review_quality.staleness import doc_key, doc_stem, doc_mtime_iso, is_doc_stale
from review_quality.cross_validation import find_stale_cross_validation
from review_quality.constants import REVIEW_QUALITY_FILENAME


def _result_payload(**overrides) -> dict:
    """Build the common result shape with sensible defaults."""
    defaults = {
        "re_review_required": False,
        "reason": "",
        "doc_modified": None,
        "last_review": None,
        "overall_status": None,
        "stale_cross_validation": [],
    }
    defaults.update(overrides)
    return defaults


def main() -> None:
    parser = cli.strict_parser(__doc__)
    cli.add_document_selectors(
        parser, spec_name=True, doc=True, category=True,
    )
    parser.set_defaults(category="spec")
    args = parser.parse_args()

    if not args.doc:
        parser.error("--doc is required")
    if not args.spec_name:
        parser.error("--spec-name / --target-name is required")

    project_root = paths.resolve_project_path(args)
    doc_directory = doc_dir_path(args.category, args.spec_name, project_root)
    doc_path = os.path.join(doc_directory, args.doc)
    quality_path = os.path.join(doc_directory, REVIEW_QUALITY_FILENAME)

    if not os.path.isfile(doc_path):
        output.miss(_result_payload(
            reason=f"Document {args.doc} does not exist yet. No re-review needed.",
        ), "No document found")
        return

    quality_data = output.safe_read_json(quality_path, default=None)
    if quality_data is None:
        output.miss(_result_payload(
            reason="No review-quality.json found. First review has not been run yet.",
        ), "No prior review")
        return
    overall_status = quality_data.get("overall_status", "INCOMPLETE")

    doc_modified_iso = doc_mtime_iso(doc_path)

    dk = doc_key(args.doc)
    doc_entry = (quality_data.get("documents") or {}).get(dk)

    if doc_entry is None or doc_entry.get("last_reviewed_at") is None:
        output.miss(_result_payload(
            reason=f"{args.doc} has never been reviewed. No stale review to invalidate.",
            doc_modified=doc_modified_iso,
            overall_status=overall_status,
        ), "Document never reviewed — no re-review needed")
        return

    review_timestamp = doc_entry["last_reviewed_at"]
    doc_modified_after_review = is_doc_stale(doc_path, quality_data, args.doc)

    stem = doc_stem(args.doc)
    stale_cross_validation = find_stale_cross_validation(quality_data, stem)

    if doc_modified_after_review:
        output.partial(_result_payload(
            re_review_required=True,
            reason=(
                f"{args.doc} was modified at {doc_modified_iso} after review at "
                f"{review_timestamp}. Re-run review before approval."
            ),
            doc_modified=doc_modified_iso,
            last_review=review_timestamp,
            overall_status=overall_status,
            stale_cross_validation=stale_cross_validation,
        ), "Re-review required")
        return

    output.success(_result_payload(
        reason="Review is current. Proceed to approval.",
        doc_modified=doc_modified_iso,
        last_review=review_timestamp,
        overall_status=overall_status,
        stale_cross_validation=stale_cross_validation,
    ), "Review is current")


if __name__ == "__main__":
    cli.run_main(main)
