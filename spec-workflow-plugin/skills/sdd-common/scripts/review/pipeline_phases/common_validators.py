"""Cross-argument validators for phase Input dataclasses.

Single authority for cross-argument invariants. Each ``Input``
dataclass owns its own invariants via ``__post_init__``; these
helpers are the functions ``__post_init__`` calls:

* :func:`check_parent_todo_pair` / :func:`check_launch_target_name`
  return an error string (or ``None``) — the shared source of truth.
* :func:`require_parent_todo_pair` / :func:`require_launch_target_name`
  wrap the checks to raise ``ValueError`` — the canonical shape Input
  dataclasses call from ``__post_init__``.
"""
from __future__ import annotations

from typing import Optional

__all__ = [
    "XOR_PAIR_MESSAGE",
    "check_parent_todo_pair",
    "check_launch_target_name",
    "require_parent_todo_pair",
    "require_launch_target_name",
]


XOR_PAIR_MESSAGE: str = (
    "--parent-todo and --gate-id must both be provided or both omitted"
)


def check_parent_todo_pair(
    parent_todo: Optional[str], gate_id: Optional[str],
) -> Optional[str]:
    """Return an error message when XOR pairing is violated, else ``None``.

    The invariant: ``--parent-todo`` and ``--gate-id`` must either
    both be provided or both be omitted. Declared on every non-ack
    phase whose Input dataclass surfaces the lifecycle fields; ack
    phases keep the invariant inexpressible by not declaring the
    fields at all.
    """
    if bool(parent_todo) != bool(gate_id):
        return XOR_PAIR_MESSAGE
    return None


def check_launch_target_name(
    category: Optional[str], target_name: Optional[str],
) -> Optional[str]:
    """Return an error message when a spec/discovery launch lacks
    ``--target-name``, else ``None``.

    Steering launches don't carry a target name; spec and discovery
    do. Encoded here so ``LaunchInput.__post_init__`` can enforce it
    without reaching into the raw argparse namespace.
    """
    if category in ("spec", "discovery") and not target_name:
        return (
            f"--target-name (or --spec-name) is required for category "
            f"'{category}'. Example: --target-name my-feature-name"
        )
    return None


def require_parent_todo_pair(
    parent_todo: Optional[str], gate_id: Optional[str],
) -> None:
    """Raise ``ValueError`` when :func:`check_parent_todo_pair` fires.

    Canonical Input-dataclass shape: ``__post_init__`` calls this; the
    base :class:`~review.phase_kit.Phase` catches ``ValueError`` at
    dispatch time and re-emits via :func:`sdd_core.output.error` so the
    agent sees the same blocked envelope the ``_guards`` loop emits.
    """
    msg = check_parent_todo_pair(parent_todo, gate_id)
    if msg:
        raise ValueError(msg)


def require_launch_target_name(
    category: Optional[str], target_name: Optional[str],
) -> None:
    """Raise ``ValueError`` when :func:`check_launch_target_name` fires."""
    msg = check_launch_target_name(category, target_name)
    if msg:
        raise ValueError(msg)
