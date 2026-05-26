"""Pipeline ack-reference-reads phase: record reference-file read receipts."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from sdd_core import output, reference_acks, reference_ledger

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from . import launch_preconditions as _lp


def _parse_references_csv(raw: str) -> list[tuple[str, str]]:
    """Parse ``name=<sha>,name=<sha>`` into ``(name, sha)`` pairs.

    Empty segments are ignored so trailing commas don't poison the list.
    Malformed segments (missing ``=``) raise a :class:`ValueError` with
    a concrete hint for the agent.
    """
    pairs: list[tuple[str, str]] = []
    for chunk in (raw or "").split(","):
        token = chunk.strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError(
                f"malformed --references entry {token!r}; expected 'name=<sha>'"
            )
        name, sha = token.split("=", 1)
        name = name.strip()
        sha = sha.strip()
        if not name or not sha:
            raise ValueError(
                f"--references entry {token!r} needs both name and SHA"
            )
        pairs.append((name, sha))
    return pairs


def _ack_single_reference_read(
    *, reference_name: str, echoed_sha256: str,
    category: str, target_name: str, project_path: str, gate_id: str,
) -> tuple[bool, str, dict]:
    """Ack a single reference read. Shared by the singular and batched
    code paths so both emit identical ledger entries and error shapes.

    Returns ``(ok, reason, diagnostic_entry)``.
    """
    pre = _lp.find_precondition(reference_name)
    if not isinstance(pre, _lp.ReferenceReadPrecondition):
        known = ", ".join(
            p.name for p in _lp.DEFAULT_REQUIRED
            if isinstance(p, _lp.ReferenceReadPrecondition)
        )
        return False, f"no reference-read precondition named {reference_name!r}; known: {known}", {
            "reference_name": reference_name,
            "echoed_sha256": echoed_sha256,
            "status": "unknown",
        }

    expected_sha = pre.expected_sha256()
    ok, reason = reference_ledger.verify_and_record_read(
        name=reference_name,
        expected_sha256=expected_sha,
        echoed_sha256=echoed_sha256,
        category=category,
        target_name=target_name,
        reference_path=pre.absolute_path(),
        project_path=project_path,
    )
    # Also record into the project-scoped ledger so subsequent gates
    # (possibly across different specs in the same checkout) don't
    # re-demand the read (see ``sdd_core.reference_acks``).
    if ok:
        reference_acks.record_ack(
            pre.absolute_path(), expected_sha,
            project_path=project_path,
            gate_id=gate_id or reference_acks.GLOBAL_GATE_ID,
        )
    entry = {
        "reference_name": reference_name,
        "expected_sha256": expected_sha,
        "echoed_sha256": echoed_sha256,
        "status": "ok" if ok else "mismatch",
    }
    if not ok:
        entry["reason"] = reason
    return ok, reason, entry


def handle_ack_reference_reads(args: argparse.Namespace) -> None:
    """Record that the agent read one or more reference files.

    ``ReferenceReadPrecondition`` relies on a pipeline-owned producer
    the agent can reach via its normal toolbelt — the IDE ``Read`` tool
    cannot append to the ledger on its own. Two invocation shapes are
    supported:

    * Singular — ``--reference-name <name> --echoed-sha256 <sha>``.
    * Batched  — ``--references name=<sha>,name=<sha>``.

    Both paths share :func:`_ack_single_reference_read`; batched calls
    short-circuit on the first mismatch and return a consolidated
    ``results`` array so the agent sees which reads landed and which
    need a retry.
    """
    ctx = PhaseContext.from_args(args)
    category = ctx.category
    target_name = ctx.target_name
    project_path = ctx.project_path
    gate_id = ctx.gate_id or reference_acks.GLOBAL_GATE_ID
    references_raw = getattr(args, "references", None)

    if references_raw:
        try:
            pairs = _parse_references_csv(references_raw)
        except ValueError as exc:
            output.error(
                str(exc),
                next_action_command=(
                    "pipeline-tick.py --phase ack-reference-reads "
                    "-- --references name=<sha>,name=<sha>"
                ),
            )
            return
        if not pairs:
            output.error(
                "--references must contain at least one 'name=<sha>' pair",
                next_action_command=(
                    "pipeline-tick.py --phase ack-reference-reads "
                    "-- --references name=<sha>,name=<sha>"
                ),
            )
            return
        results: list[dict] = []
        failed: list[dict] = []
        for name, sha in pairs:
            ok, _reason, entry = _ack_single_reference_read(
                reference_name=name, echoed_sha256=sha,
                category=category, target_name=target_name,
                project_path=project_path, gate_id=gate_id,
            )
            results.append(entry)
            if not ok:
                failed.append(entry)
        payload = {
            "results": results,
            "recorded_count": len(results) - len(failed),
            "failed_count": len(failed),
        }
        message = (
            f"Recorded {len(results) - len(failed)}/{len(results)} "
            "reference read(s)"
        )
        if failed:
            payload["status"] = "partial"
            output.partial(payload, message)
        else:
            payload["status"] = "ok"
            output.success(payload, message)
        return

    reference_name = args.reference_name
    echoed_sha256 = args.echoed_sha256

    if not reference_name:
        output.error(
            "--reference-name is required for the ack-reference-reads phase"
        )
        return
    if not echoed_sha256:
        output.error(
            "--echoed-sha256 is required for the ack-reference-reads phase"
        )
        return

    ok, reason, entry = _ack_single_reference_read(
        reference_name=reference_name, echoed_sha256=echoed_sha256,
        category=category, target_name=target_name,
        project_path=project_path, gate_id=gate_id,
    )
    if entry.get("status") == "unknown":
        output.error(
            f"No reference-read precondition named {reference_name!r}",
            hint=reason,
        )
        return
    if not ok:
        output.result(
            {
                "outcome": "mismatch",
                "reason": reason,
                "reference_name": reference_name,
                "expected_sha256": entry.get("expected_sha256"),
                "echoed_sha256": echoed_sha256,
            },
            f"ack-reference-reads rejected: {reason}",
            exit_code=1,
        )
        return
    output.success(
        {
            "status": "ok",
            "reference_name": reference_name,
            "recorded_sha256": echoed_sha256,
        },
        f"Reference read recorded for {reference_name}",
    )


@dataclass
class AckReferenceReadsInput(PhaseInput):
    """Typed input for the ``ack-reference-reads`` phase.

    Phase-specific flags only — lifecycle fields (``category``,
    ``target_name``, ``project_path``, ``parent_todo``, ``gate_id``)
    live on the common parent parser and are omitted here. The
    XOR-pairing invariant is *inexpressible* on an ack-phase Input
    rather than enforced by an exemption set.
    """

    reference_name: str = field(
        default=None, metadata={
            "help": (
                "Name of the ReferenceReadPrecondition whose read "
                "receipt this call is recording."
            ),
        },
    )
    echoed_sha256: str = field(
        default=None, metadata={
            "help": (
                "SHA-256 the agent echoed after reading the reference "
                "file. Compared against the content hash of the "
                "resolved path; the ledger is appended only on "
                "agreement."
            ),
        },
    )
    references: str = field(
        default=None, metadata={
            "metavar": "name=<sha>,name=<sha>",
            "help": (
                "Batched form of --reference-name / --echoed-sha256. "
                "Comma-separated ``name=<sha>`` pairs; each pair is "
                "verified and recorded in one call so the cold launch "
                "gate reaches --phase launch in three shell calls "
                "instead of five."
            ),
        },
    )


@phase(
    name="ack-reference-reads",
    emits=frozenset(),
    help="Record reference-file read receipts against the ledger",
    description=__doc__,
)
class AckReferenceReadsPhase(Phase):
    """Ack-flavoured phase — records reference-file read receipts."""

    Input = AckReferenceReadsInput

    def handle(self, args: argparse.Namespace) -> None:
        handle_ack_reference_reads(args)
