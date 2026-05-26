"""Closed enumeration of review skills.

Inheriting from ``str`` keeps the wire format stable
(``ReviewSkill.SPEC.value == "sdd-review-spec-docs"``) while making
every callsite type-checkable. Any code path that wants a review-skill
name reaches for :func:`ReviewSkill.for_category` (the single dispatch
point) — adding a string default reintroduces the skill-name drift
class this enum exists to eliminate.

The companion lint
``internal_lints/review_skill_no_string_default`` blocks
``dict.get("review_skill", <string>)`` and DEFAULT_REVIEW_SKILL-style
constants outside this module so the structural guarantee survives
future call sites.
"""
from __future__ import annotations

from enum import Enum
from typing import Final


__all__ = [
    "ReviewSkill",
    "skill_for_category",
]


class ReviewSkill(str, Enum):
    """Closed enumeration of canonical review skill names."""

    STEERING = "sdd-review-steering-docs"
    SPEC = "sdd-review-spec-docs"
    DISCOVERY = "sdd-review-prd"

    # Python 3.11 changed str() on (str, Enum) members to return
    # "ClassName.MEMBER" instead of the value; force the wire literal
    # so f-strings keep emitting the canonical skill name.
    def __str__(self) -> str:
        return str.__str__(self)

    @classmethod
    def for_category(cls, category: str) -> "ReviewSkill":
        """Single dispatch point — category to canonical review skill.

        Unknown categories raise :class:`KeyError`. Callers must not
        introduce a fallback default; passing the wrong category is a
        bug, not an environmental condition.
        """
        return _CATEGORY_TO_SKILL[category]

    @classmethod
    def from_value(cls, value: str) -> "ReviewSkill":
        """Coerce a wire-format string into a :class:`ReviewSkill`.

        Use at deserialization boundaries (cached gate session,
        pipeline payloads). Unknown values raise :class:`ValueError`.
        """
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(
                f"Unknown review skill {value!r}; expected one of "
                f"{[s.value for s in cls]}"
            ) from exc


_CATEGORY_TO_SKILL: Final[dict[str, ReviewSkill]] = {
    "steering": ReviewSkill.STEERING,
    "spec": ReviewSkill.SPEC,
    "discovery": ReviewSkill.DISCOVERY,
    "prd": ReviewSkill.DISCOVERY,
}


def skill_for_category(category: str) -> ReviewSkill:
    """Module-level alias of :meth:`ReviewSkill.for_category`."""
    return ReviewSkill.for_category(category)
