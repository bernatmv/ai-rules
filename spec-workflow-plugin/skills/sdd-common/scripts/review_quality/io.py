"""Input loading, existing artifact loading, and writing."""
from __future__ import annotations

import json
import os
import sys

import migrations.review_quality  # noqa: F401 — registers steps on import
from migrations import migrate

from .registry import (
    SCHEMA_VERSION,
    _SCRIPT_OWNED_KEYS,
)
from .paths import safe_open
from sdd_core import output
from sdd_core.paths import WORKFLOW_DIR


def load_input(path: str | None) -> dict:
    """Read and parse AI assessment JSON. Strip script-owned keys. Exit 1/2 on error."""
    try:
        if path is None:
            raw = sys.stdin.read()
        else:
            with safe_open(path) as f:
                raw = f.read()
        if not raw.strip():
            output.error("Input is empty")
        raw_input = json.loads(raw)
    except json.JSONDecodeError as e:
        output.error(f"Invalid JSON in input: {e}")
    for k in _SCRIPT_OWNED_KEYS:
        raw_input.pop(k, None)
    return raw_input


def load_existing(path: str) -> dict | None:
    """Read existing artifact if present. Return None if missing."""
    if not os.path.isfile(path):
        return None
    try:
        existing = output.safe_read_json(path)
    except ValueError as e:
        output.warn(f"could not read existing artifact at {path!r}: {e}")
        return None
    if existing is None:
        return None

    existing_ver = str(existing.get("schema_version", "1.0.0"))
    try:
        ex_major = int(existing_ver.split(".")[0])
        our_major = int(SCHEMA_VERSION.split(".")[0])
    except (ValueError, IndexError):
        ex_major = 0
        our_major = 1
    if ex_major > our_major:
        output.error(
            f"Existing artifact has incompatible schema_version {existing_ver!r}"
            f" (script supports {SCHEMA_VERSION})"
        )
    gen_at = existing.get("generated_at", "")
    if gen_at:
        try:
            from datetime import datetime, timezone
            artifact_dt = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
            if artifact_dt > datetime.now(timezone.utc):
                output.warn(
                    f"clock skew detected — existing artifact generated_at"
                    f" {gen_at!r} is in the future"
                )
        except ValueError:
            pass

    return migrate(existing, SCHEMA_VERSION)


def write_artifact(path: str, artifact: dict) -> None:
    """makedirs + atomic write + schema_version verify. Exit 2 on failure."""
    if artifact.get("schema_version") != SCHEMA_VERSION:
        output.error(
            f"schema_version mismatch: artifact has {artifact.get('schema_version')!r},"
            f" expected {SCHEMA_VERSION!r}",
            exit_code=2,
        )
    try:
        output.atomic_write_json(path, artifact, verify_key="schema_version")
    except (OSError, IOError) as e:
        output.error(f"failed to write artifact to {path!r}: {e}", exit_code=2)
