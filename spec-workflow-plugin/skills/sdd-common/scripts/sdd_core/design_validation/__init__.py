"""design.md antipattern validation — public facade.

Mirrors :mod:`sdd_core.requirements_validation`. Rule definitions live
in ``sdd_core/data/design_antipatterns.yaml``; the YAML is the open
extension surface.
"""
from __future__ import annotations

from .ruleset import load_ruleset
from .types import DATA_FILE, Finding, ValidationOutcome
from .validate import validate_content

__all__ = [
    "DATA_FILE",
    "Finding",
    "ValidationOutcome",
    "load_ruleset",
    "validate_content",
]
