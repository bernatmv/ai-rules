"""Compliance rating enum — single source of truth for compliance levels."""
from __future__ import annotations

from enum import IntEnum

__all__ = ["ComplianceRating"]


class ComplianceRating(IntEnum):
    """Template compliance levels with exit-code semantics.

    Values double as process exit codes: ``sys.exit(rating)`` works because
    ``int(ComplianceRating.PARTIAL)`` returns ``1``.
    """
    COMPLIANT = 0
    PARTIAL = 1
    NON_COMPLIANT = 2

    @property
    def tier1_label(self) -> str:
        """Tier 1 score label used by review_quality (PASS / PARTIAL / FAIL)."""
        return _TIER1_LABELS[self]


_TIER1_LABELS: dict[ComplianceRating, str] = {
    ComplianceRating.COMPLIANT:     "PASS",
    ComplianceRating.PARTIAL:       "PARTIAL",
    ComplianceRating.NON_COMPLIANT: "FAIL",
}
