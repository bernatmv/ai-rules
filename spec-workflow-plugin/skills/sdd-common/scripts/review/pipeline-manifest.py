#!/usr/bin/env python3
"""Pipeline capability manifest.

Emits the capability manifest the host agent consumes at session
init to verify it has an adapter for every action kind the pipeline
might emit, and that every ``prompt_type`` referenced by an
:kind:`AskQuestion` / :kind:`Instruction` action resolves in
``prompt-registry.json``.

The manifest is a pure function of the in-repo schema + registry. No
session state is read — running it is a dependency-free syntax check:

* ``action_kinds`` = :class:`~review.schema.ActionKind` members.
* ``prompt_types`` = keys of ``prompts`` in ``prompt-registry.json``.
* ``envelope_version`` = :data:`~review.schema.ENVELOPE_VERSION`.

Usage:
  pipeline-manifest.py                    # JSON to stdout
  pipeline-manifest.py --output <path>    # write file instead

Exits 0 when the manifest was emitted. Non-zero exit codes are
reserved for future ``--verify`` modes that cross-check emitted
envelopes against the manifest.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import json
import sys

from sdd_core import cli, output
from sdd_core.prompts import load_registry

from review.schema import ActionKind, ENVELOPE_VERSION


def build_parser() -> argparse.ArgumentParser:
    """Return the argparse parser — exported so
    ``test_next_action_command_parses`` can round-trip emitted
    invocations."""
    parser = cli.strict_parser(
        __doc__,
        epilog=(
            "Examples:\n"
            "  pipeline-manifest.py\n"
            "  pipeline-manifest.py --output /tmp/pipeline-manifest.json\n"
        ),
    )
    parser.add_argument(
        "--output", default=None,
        help="Write the manifest JSON to this path instead of stdout.",
    )
    return parser


def build_manifest() -> dict:
    """Return the capability manifest dict.

    Alphabetised inside each list for stable diffs — manifest drift is
    reviewed as a text diff so deterministic ordering keeps the review
    surface tight.
    """
    try:
        registry = load_registry()
    except FileNotFoundError:
        prompt_types: list[str] = []
    else:
        prompt_types = sorted((registry.get("prompts") or {}).keys())
    return {
        "envelope_version": ENVELOPE_VERSION,
        "action_kinds": sorted(k.value for k in ActionKind),
        "prompt_types": prompt_types,
    }


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    manifest = build_manifest()
    payload = json.dumps(manifest, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.write("\n")
        output.success(
            {"output": args.output, **manifest},
            f"Manifest written to {args.output}",
        )
        return
    # stdout path — single-line JSON to keep the NDJSON stream used by
    # pipeline/run parseable without mode switching.
    sys.stdout.write(payload)
    sys.stdout.write("\n")


if __name__ == "__main__":
    cli.run_main(main)
