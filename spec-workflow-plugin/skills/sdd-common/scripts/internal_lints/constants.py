"""Subsystem-scoped invariants for the lint baseline format.

The on-disk shape of ``baselines.json`` and the canonical
``<file>::<line>::<reason>`` key encoding are documented here in one
place. A future format bump (adding a ``severity`` column, renaming
the schema version, etc.) flows through these constants.
"""
from __future__ import annotations

__all__ = [
    "BASELINE_MANIFEST_FILENAME",
    "BASELINE_SCHEMA_VERSION",
    "BASELINE_KEY_SEPARATOR",
    "BASELINE_DEFAULT_REASON",
]


# Filename of the consolidated lint-baseline manifest. Lives under
# :mod:`internal_lints` next to the lint modules themselves.
BASELINE_MANIFEST_FILENAME = "baselines.json"

# Manifest schema version. Increment + bump call sites when changing
# the on-disk shape (e.g. adding a new column to ``entries``).
BASELINE_SCHEMA_VERSION = "1.0.0"

# Canonical separator used in the ``<file>::<line>::<reason>`` key
# format. Consumers ride :func:`internal_lints.baseline.key_for` /
# :func:`internal_lints.baseline.parse_key` rather than the literal.
BASELINE_KEY_SEPARATOR = "::"

# Default ``reason`` populated when a finding has no explicit
# annotation; surfaced unchanged in the manifest so ``--prune`` round-
# trips do not change unrelated entries.
BASELINE_DEFAULT_REASON = "no rationale"
