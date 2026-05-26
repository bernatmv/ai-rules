#!/usr/bin/env python3
"""Count effective lines in a document (non-empty, non-frontmatter).

Usage:
    count-effective-lines.py <path> [<path> ...]
    count-effective-lines.py --file PATH [--file PATH ...]
    count-effective-lines.py --category <c> --target-name <n> --doc-list a,b,c

Exit code: 0 on success, 1 on usage/file error.
"""

import _bootstrap  # noqa: F401

import collections

from skill_helpers import (
    iter_effective_lines, iter_line_categories, safe_open,
)
from sdd_core import output, cli


__sdd_manifest__ = {
    "summary": "Count effective (non-empty, non-frontmatter) lines in a document",
    "verbs": [
        "<path> [<path> ...]",
        "--file <path> [--file <path> ...]",
        "--category <c> --target-name <n> --doc-list a,b,c",
    ],
    "flags": [
        "--file", "--category", "--target-name",
        "--spec-name", "--doc-list", "--workspace", "--verbose",
    ],
}


def _breakdown(filepath: str) -> dict:
    with safe_open(filepath) as fh:
        counts = collections.Counter(
            cat for _, _, _, cat in iter_line_categories(fh.read())
        )
    return {
        "effective":            counts["effective"],
        "skipped_blank":        counts["blank"],
        "skipped_frontmatter":  counts["frontmatter"],
        "skipped_code_block":   counts["code_block"],
        "skipped_html_comment": counts["html_comment"],
        "total_raw":            sum(counts.values()),
    }


def main():
    parser = cli.strict_parser(__doc__)
    cli.add_document_selectors(
        parser,
        file=True, file_repeatable=True,
        positional_files=True,
        spec_name=True,
        category=True,
        doc_list=True,
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help=(
            "Emit per-file category breakdown (effective / blank / "
            "frontmatter / code_block / html_comment)."
        ),
    )
    args = parser.parse_args()

    files = cli.resolve_files(args)

    results = []
    for f in files:
        entry = {"file": f, "count": sum(1 for _ in iter_effective_lines(f))}
        if args.verbose:
            entry["breakdown"] = _breakdown(f)
        results.append(entry)
    total = sum(r["count"] for r in results)
    if len(results) == 1:
        payload = {
            "count": results[0]["count"], "file": results[0]["file"],
            "results": results, "total": total,
        }
        if args.verbose:
            payload["breakdown"] = results[0]["breakdown"]
        output.success(payload, f"{total} effective lines")
    else:
        output.success(
            {"results": results, "total": total},
            f"{len(results)} file(s) counted, {total} total",
        )


if __name__ == "__main__":
    cli.run_main(main)
