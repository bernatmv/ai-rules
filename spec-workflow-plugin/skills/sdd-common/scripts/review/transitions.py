"""Declarative phase-transition graph — the single authority.

Every phase that advances the review pipeline declares the set of
phases it may transition to. The handler still decides *which* member
of the set to pick at runtime (based on findings count, user choice,
…), but the enumerable **range** of every transition is authoritative
here.

Why a set and not a lambda:

* Enumerable without a live envelope. Property tests
  (`tests/test_transitions_reachability.py`) walk the graph from
  ``launch`` and verify reachability, terminal correctness, and
  registry parity without synthesising envelopes.
* ``guards.py`` derives ``allowed_previous(X)`` on demand from this
  graph (the inverse transition), so a phase cannot drift from the
  single authority.
* The ``@phase(emits=...)`` set in :mod:`review.phase_kit` is a
  derived shadow: a property test asserts
  ``emits == TRANSITIONS[P]`` for every decorator-migrated phase,
  failing CI if either side drifts.

Adding / removing a transition = edit this dict. Tests, guards, and
the registration surface all consume :data:`TRANSITIONS` directly.

Ack-flavoured phases (``ack-calls``, ``ack-reference-reads``,
``ack-post-change-review``, ``ack-advisories``) and standalone entry
points (``code-review-launch``, ``pre-launch-check``) are
*never-next*: they only enter the graph when an earlier phase emits a
matching required-tool-call, or when invoked directly by outer
workflow. They appear in :data:`ACK_PHASES` / :data:`ENTRY_PHASES` so
property tests can special-case them without hard-coding names
elsewhere.
"""
from __future__ import annotations

from typing import Final

__all__ = [
    "TRANSITIONS",
    "ACK_PHASES",
    "ENTRY_PHASES",
    "TERMINAL_PHASES",
    "all_phases",
    "allowed_previous",
    "reachable_from",
    "phase_key",
]


def phase_key(phase: str) -> str:
    """Return the snake_case ``phase_commands`` key for a kebab phase name.

    Single owner for the conversion so every phase handler shares one
    rule (``check-revalidation`` → ``check_revalidation``). Avoids
    inline ``replace("-", "_")`` calls drifting across handlers.
    """
    return phase.replace("-", "_")


# ---------------------------------------------------------------------------
# Authoritative graph
# ---------------------------------------------------------------------------

TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    # Launch → post-review is always the first real transition.
    "launch": frozenset({"post-review"}),
    # Post-review branches on findings_count.
    "post-review": frozenset({"post-fix", "pre-approval"}),
    # Post-fix branches on (user_choice, can_continue).
    "post-fix": frozenset({"check-revalidation", "pre-approval"}),
    # Re-validation branches on staleness + cycle budget.
    "check-revalidation": frozenset({"launch", "pre-approval"}),
    # Pre-approval either hands off to the external approval flow or
    # re-enters launch for re-review when blocking docs exist.
    "pre-approval": frozenset({"approval", "launch"}),
    # ``approval`` is outside the review-pipeline scripts (see
    # ``approval/request.py``) but is still part of the agent-visible
    # graph because the gate stores it as the next expected phase.
    # Its only forward transition is ``complete``.
    "approval": frozenset({"complete"}),
    # Terminal — cleans up the gate session.
    "complete": frozenset(),
}


# Ack phases are injected into the agent's next-action chain when a
# phase emits required_tool_calls; they never sit on
# ``TRANSITIONS[X]`` for any X because the next "real" phase is
# always preserved via the session.
ACK_PHASES: Final[frozenset[str]] = frozenset({
    "ack-advisories",
    "ack-calls",
    "ack-post-change-review",
    "ack-reference-reads",
    # Operator reset hatch for the project-scoped reference-acks
    # ledger. Not on the review-graph; standalone utility phase.
    "reset-reference-acks",
})


# Standalone entry points — executed directly by outer workflows, not
# reached via graph traversal.
ENTRY_PHASES: Final[frozenset[str]] = frozenset({
    "code-review-launch",
    "pre-launch-check",
    "update-launch",
    # Operator reset hatch: discards a gate's session state when the
    # caller chooses not to keep it (e.g. after an
    # ``abandoned_prior_gate`` advisory). Not on the forward graph.
    "discard",
})


# Phases that terminate the graph (no outgoing transitions).
TERMINAL_PHASES: Final[frozenset[str]] = frozenset(
    name for name, nexts in TRANSITIONS.items() if not nexts
)


# ---------------------------------------------------------------------------
# Derivations
# ---------------------------------------------------------------------------


def all_phases() -> frozenset[str]:
    """Return every phase name the authority knows about.

    The union of :data:`TRANSITIONS` keys, :data:`ACK_PHASES`, and
    :data:`ENTRY_PHASES` — this is the enumeration every property test
    consumes. Adding a phase is a one-line edit in exactly one of
    these three.
    """
    return frozenset(TRANSITIONS).union(ACK_PHASES).union(ENTRY_PHASES)


def allowed_previous(expected: str) -> frozenset[str]:
    """Return the set of phases allowed to run when the gate expects
    ``expected`` next.

    This is the inverse of :data:`TRANSITIONS`: when the session
    recorded ``required_next_phase = expected``, the current phase
    must either be ``expected`` itself (normal forward step) or a
    phase whose declared range includes ``expected`` (catches the
    "re-enter the previous step from a re-review loop" case that
    ``guards._PHASE_ALIASES`` used to encode by hand).

    Derived on every call rather than cached so the TRANSITIONS dict
    is the sole source — no second table to keep in sync. The cost is
    a single ``dict`` scan; negligible compared to the cost of a
    stale cache silently accepting a drifting phase.
    """
    previous = {
        phase for phase, nexts in TRANSITIONS.items() if expected in nexts
    }
    previous.add(expected)
    return frozenset(previous)


def reachable_from(start: str) -> frozenset[str]:
    """Return every phase reachable from ``start`` via the graph.

    Breadth-first traversal — used by the reachability property test
    to prove every non-entry, non-ack phase is reachable from
    ``launch``. Runs in O(|phases|); the dict is small.
    """
    seen: set[str] = set()
    pending = [start]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(TRANSITIONS.get(node, frozenset()))
    return frozenset(seen)
