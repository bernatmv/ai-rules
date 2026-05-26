"""Internal lints: CI/developer ratchets over SDD's own source.

Not part of any agent workflow. See ``README.md`` for the role
declaration and the rule inventory (Group A: Python source-quality;
Group B: SKILL.md content lints).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "LintFinding",
]


@dataclass(frozen=True)
class LintFinding:
    """One issue surfaced by a lint."""

    rule_id: str
    severity: str
    file: str
    line: int
    message: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict:
        payload: dict = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }
        if self.extra:
            payload["extra"] = self.extra
        return payload
