"""Governance guards: fix-decision enforcement and contradiction detection.

Split from prompts.py for single-responsibility: prompt rendering is
independent of governance decision logic.
"""
from __future__ import annotations

from .matchers import WordMatcher

__all__ = [
    "require_fix_decision",
    "is_contradictory_feedback",
    "AFFIRM_WORDS",
]

AFFIRM_WORDS = WordMatcher(
    ["good", "ok", "okay", "fine", "looks good", "lgtm",
     "approve", "great", "nice", "perfect", "yes", "yep", "sure"],
    boundary="start",
)


def require_fix_decision(fix_prompt_presented: bool) -> None:
    """Guard: raises if the fix-decision prompt was not yet presented.

    Call before any document edit during a review gate. Ensures the
    review-fix-issues prompt was presented and the user chose a fix action.
    """
    if not fix_prompt_presented:
        raise RuntimeError(
            "Cannot modify documents during review gate without presenting "
            "the review-fix-issues prompt first. Present the prompt via "
            "AskQuestion, then act on the user's selection."
        )


def is_contradictory_feedback(selection_id: str, feedback: str) -> bool:
    """True if free-text feedback contradicts a revision/rejection selection.

    Callers should present the 'confirm-intent-override' prompt when True.
    """
    if selection_id not in ("needs_revision", "reject"):
        return False
    return AFFIRM_WORDS.match(feedback) is not None
