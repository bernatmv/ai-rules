"""Pipeline reset-reference-acks phase: clear the project-scoped ledger.

Reset hatch for the project-scoped reference-ack ledger; flushes every
cached ``(path, sha)`` pair so the next launch re-demands the reads.
Operators invoke this when the automated invalidation (sha mismatch →
re-demand) isn't granular enough for a debugging scenario.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from sdd_core import output, reference_acks

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from .constants import (
    ADVISORY_CODE_REFERENCE_ACKS_CLEARED,
    ADVISORY_LEVEL_INFO,
    KEY_ADVISORIES,
)


def handle_reset_reference_acks(args: argparse.Namespace) -> None:
    ctx = PhaseContext.from_args(args)
    removed = reference_acks.reset(project_path=ctx.project_path)
    if removed is None:
        output.success(
            {"status": "noop", "path": reference_acks.acks_path(ctx.project_path)},
            "No reference-acks.json to remove",
        )
        return
    output.success(
        {
            "status": "cleared",
            "path": removed,
            KEY_ADVISORIES: [
                output.advisory(
                    f"Cleared reference-acks ledger at {removed}",
                    level=ADVISORY_LEVEL_INFO,
                    code=ADVISORY_CODE_REFERENCE_ACKS_CLEARED,
                ),
            ],
        },
        "reference-acks.json cleared",
    )


@dataclass
class ResetReferenceAcksInput(PhaseInput):
    """Typed input for the ``reset-reference-acks`` phase."""


@phase(
    name="reset-reference-acks",
    emits=frozenset(),
    help="Clear the project-scoped reference-acks ledger",
    description=__doc__,
)
class ResetReferenceAcksPhase(Phase):
    Input = ResetReferenceAcksInput

    def handle(self, args: argparse.Namespace) -> None:
        handle_reset_reference_acks(args)
