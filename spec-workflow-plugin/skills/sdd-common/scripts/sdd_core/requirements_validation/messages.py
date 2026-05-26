"""User-facing message formatting for findings.

Per-group copy lives in ``requirements_antipatterns.yaml`` (``message_template``).
Keeping the template in YAML alongside the rest of the group data means
adding a new canonical group touches exactly one file instead of
rippling across YAML, ``GROUP_FIX_HINTS``, and a Python switch.
"""
from __future__ import annotations

from typing import Any

__all__ = ["build_message"]


_FALLBACK_TEMPLATE = "{group}: {match}"


def build_message(
    group: dict[str, Any],
    *,
    group_name: str,
    rule: str,
    match: str,
) -> str:
    """Format the user-facing message for a finding.

    ``group`` is the compiled group dict produced by
    :func:`ruleset.load_ruleset`. When the group declares a
    ``message_template`` the tokens ``{group}``/``{rule}``/``{match}``
    are substituted; otherwise a ``"group: match"`` summary is emitted
    so missing templates surface a legible string.
    """
    template = group.get("message_template") or _FALLBACK_TEMPLATE
    return template.format(group=group_name, rule=rule, match=match)
