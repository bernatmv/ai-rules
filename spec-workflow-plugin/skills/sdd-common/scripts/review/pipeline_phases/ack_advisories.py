"""Pipeline ack-advisories phase: record advisory-banner echoes against the ledger."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from sdd_core import output

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from . import launch_preconditions as _lp


def handle_ack_advisories(args: argparse.Namespace) -> None:
    """Record that the agent echoed an advisory banner verbatim.

    Append-only marker keyed by advisory name — the
    :class:`AdvisoryEchoPrecondition` gate reads the ledger and skips
    this advisory once the entry exists. ``--echoed-sha256`` is stored
    in the ledger extras so auditors can match the echo against the
    advisory banner hash.
    """
    ctx = PhaseContext.from_args(args)
    category = ctx.category
    target_name = ctx.target_name
    project_path = ctx.project_path
    advisory_name = args.advisory_name
    echoed_sha256 = args.echoed_sha256

    if not advisory_name:
        output.error(
            "--advisory-name is required for --phase ack-advisories"
        )
        return

    _lp.mark_advisory_echoed(
        advisory_name=advisory_name,
        category=category,
        target_name=target_name,
        project_path=project_path,
        echoed_sha256=echoed_sha256,
    )

    output.success(
        {
            "status": "ok",
            "advisory_name": advisory_name,
            "recorded_sha256": echoed_sha256,
        },
        f"Advisory echo recorded for {advisory_name}",
    )


@dataclass
class AckAdvisoriesInput(PhaseInput):
    """Typed input for the ``ack-advisories`` phase.

    Phase-specific flags only — lifecycle fields live on the common
    parent parser and are omitted from this dataclass so the ack-phase
    contract is enforced structurally (rather than via an opt-out set).
    """

    advisory_name: str = field(
        default=None, metadata={
            "help": (
                "Name of the advisory whose banner this call is "
                "recording as echoed."
            ),
        },
    )
    echoed_sha256: str = field(
        default=None, metadata={
            "help": (
                "SHA-256 the agent echoed after presenting the advisory "
                "banner. Stored in ledger extras."
            ),
        },
    )


@phase(
    name="ack-advisories",
    emits=frozenset(),
    help="Record advisory-banner echoes against the ledger",
    description=__doc__,
)
class AckAdvisoriesPhase(Phase):
    """Ack-flavoured phase — records advisory-banner echoes."""

    Input = AckAdvisoriesInput

    def handle(self, args: argparse.Namespace) -> None:
        handle_ack_advisories(args)
