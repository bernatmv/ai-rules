#!/usr/bin/env python3
"""Print canonical cross-validation pair keys for a review type.

Single source of truth consumers (agent-facing reference docs,
sub-agent prompt composers, ad-hoc debugging) should invoke this
script rather than restating the canonical list inline.

Usage:
  review_quality/print-pair-keys.py --type spec
  review_quality/print-pair-keys.py --type steering
  review_quality/print-pair-keys.py --type prd
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from sdd_core import cli, output
from review_quality.registry_helpers import canonical_cross_validation_keys

__sdd_manifest__ = {
    "summary": "Print canonical cross-validation pair keys for a review type",
    "verbs": [
        "--type spec|steering|prd",
    ],
    "flags": ["--type", "--workspace"],
}


def main() -> None:
    parser = cli.strict_parser(__doc__ or "")
    parser.add_argument(
        "--type", required=True, choices=("spec", "steering", "prd"),
        help="Review type whose pair keys should be printed.",
    )
    args = parser.parse_args()

    keys = sorted(canonical_cross_validation_keys(args.type))
    output.success(
        {"review_type": args.type, "pair_keys": keys},
        f"{len(keys)} canonical pair keys for {args.type}",
    )


if __name__ == "__main__":
    cli.run_main(main)
