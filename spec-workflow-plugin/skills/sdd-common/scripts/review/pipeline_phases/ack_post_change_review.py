"""Pipeline ack-post-change-review phase: record post-change-review echoes."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from sdd_core import output

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from . import launch_preconditions as _lp


def handle_ack_post_change_review(args: argparse.Namespace) -> None:
    """Record that the agent presented the post-change-review prompt.

    Append-only marker — the precondition check reads the ledger and
    skips the gate once this entry exists. All verification logic lives
    in :mod:`launch_preconditions`; this handler just writes the line.
    """
    ctx = PhaseContext.from_args(args)
    category = ctx.category
    target_name = ctx.target_name
    project_path = ctx.project_path
    gate_id = args.gate_id or "default"
    prompt_sha256 = getattr(args, "presented_hash", None)

    _lp.mark_post_change_review_acked(
        category=category,
        target_name=target_name,
        gate_id=gate_id,
        project_path=project_path,
        prompt_sha256=prompt_sha256,
    )

    output.success(
        {
            "ok": True,
            "gate_id": gate_id,
            "prompt_sha256": prompt_sha256,
        },
        f"post-change-review acknowledged for gate {gate_id}",
    )


@dataclass
class AckPostChangeReviewInput(PhaseInput):
    """Typed input for the ``ack-post-change-review`` phase.

    Phase-specific flags only — lifecycle fields live on the common
    parent parser and are omitted here so the ack-phase contract is
    enforced structurally.
    """

    presented_hash: str = field(
        default=None, metadata={
            "help": (
                "SHA-256 of the post-change-review prompt the agent "
                "actually presented. Recorded in the ledger so auditors "
                "can verify the presented prompt matches the registry."
            ),
        },
    )


@phase(
    name="ack-post-change-review",
    emits=frozenset(),
    help="Record post-change-review prompt echoes against the ledger",
    description=__doc__,
)
class AckPostChangeReviewPhase(Phase):
    """Ack-flavoured phase — records post-change-review prompt echoes."""

    Input = AckPostChangeReviewInput

    def handle(self, args: argparse.Namespace) -> None:
        handle_ack_post_change_review(args)
