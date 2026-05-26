#!/usr/bin/env python3
"""Compute SHA-256 of a file, emitting a JSON envelope or raw hex.

Usage:
  util/sha256.py --file <path>           # JSON envelope
  util/sha256.py --file <path> --raw     # bare hex for shell substitution

Exit 0 on success; 1 on missing/unreadable file.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import hashlib
import sys
from pathlib import Path

from sdd_core import cli, output

MISSING_FILE_SENTINEL = "MISSING_FILE"

__sdd_manifest__ = {
    "summary": "Compute SHA-256 of a file (for reference-ack shell chains)",
    "verbs": [
        "--file <path>",
        "--file <path> --raw",
    ],
    "flags": ["--file", "--raw", "--workspace"],
}


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = cli.strict_parser(__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument(
        "--raw", action="store_true",
        help="Emit just the hex digest (for $(...) shell substitution).",
    )
    args = parser.parse_args()

    if not args.file.is_file():
        if args.raw:
            print(MISSING_FILE_SENTINEL)
            sys.exit(1)
        output.error(
            f"File not found: {args.file}",
            hint=(
                "Pass an absolute path; for reference-ack use the path "
                "emitted in next_action_sequence."
            ),
        )
        return

    digest = _hash(args.file)
    if args.raw:
        print(digest)
        return
    output.success(
        {"file": str(args.file), "sha256": digest},
        f"sha256: {digest[:16]}…",
    )


if __name__ == "__main__":
    cli.run_main(main)
