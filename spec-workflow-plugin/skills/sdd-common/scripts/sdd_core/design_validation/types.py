"""Public types and data file location for the design validator."""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

__all__ = ["DATA_FILE", "Finding", "ValidationOutcome"]

DATA_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "design_antipatterns.yaml"
)


class Finding(TypedDict, total=False):
    severity: str
    rule: str
    line: int
    message: str
    suggestion: "str | None"


class ValidationOutcome(TypedDict):
    result: str
    counts: dict[str, int]
    issues: list[Finding]
