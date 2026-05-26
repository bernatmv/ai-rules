"""YAML-backed ruleset loader for design antipatterns.

Mirrors the requirements_validation ruleset shape so future rules
land as YAML edits, not code.
"""
from __future__ import annotations

from typing import Any

from ..deps import require_pyyaml
from .types import DATA_FILE

__all__ = ["load_ruleset"]


def load_ruleset() -> dict[str, Any]:
    """Return the parsed YAML ruleset.

    Raises ``FileNotFoundError`` when the data file is absent so a stale
    install is surfaced immediately rather than silently skipping checks.
    """
    yaml = require_pyyaml()

    if not DATA_FILE.is_file():
        raise FileNotFoundError(
            f"design_antipatterns.yaml missing at {DATA_FILE}; "
            "the lint cannot run without its rule set."
        )
    with DATA_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
