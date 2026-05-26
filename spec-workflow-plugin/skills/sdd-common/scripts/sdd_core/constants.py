"""Cross-module non-path literals.

Naming convention (single source of truth):

* Path-shaped values (filenames, dirnames, glob patterns) live in
  :mod:`sdd_core.paths`.
* Non-path cross-module literals (timestamp formats, fixed
  directory-name fragments) live in this module.
* Subsystem-scoped invariants (lint baseline format, key separators)
  live in ``<subsystem>/constants.py`` under that subsystem's
  directory (e.g. :mod:`internal_lints.constants`).
* Module-private magic numbers stay in their owning module; promote
  to module-level ``UPPERCASE`` constants when cross-module callers
  benefit (e.g. :data:`sdd_core.sub_agent_prompts.PROMPT_TRUNCATE_LINES`).
"""
from __future__ import annotations

__all__ = [
    "BACKUP_ROOT_DIR",
    "BACKUP_TIMESTAMP_FORMAT",
]


# Operator-visible directory carrying templates / state replaced by
# `sdd_core.security.state.atomic_backup_then_replace`. Callers that
# want the canonical layout assemble the path as
# ``<workflow_root>/<STATE_DIR_NAME>/<BACKUP_ROOT_DIR>/templates-<ts>/``.
BACKUP_ROOT_DIR = ".backup"

# Filesystem-safe ISO-8601 timestamp (no `:` so the fragment is valid
# on Windows; UTC marker preserves audit semantics). Callers compose
# via ``datetime.now(timezone.utc).strftime(BACKUP_TIMESTAMP_FORMAT)``.
BACKUP_TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%SZ"
