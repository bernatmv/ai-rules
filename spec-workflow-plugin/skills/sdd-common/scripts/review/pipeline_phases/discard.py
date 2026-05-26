"""Pipeline discard phase: drop a named gate's session + staging state.

Operator-facing reset hatch invoked after an ``abandoned_prior_gate``
advisory or whenever the caller decides not to carry a pending gate
forward. The phase is read-only with respect to the gate it does *not*
match: when ``--gate-id`` disagrees with the recorded session the
handler emits an informational ``preserved`` envelope rather than
deleting state the operator did not name.

The phase deletes:

* ``.sdd-state/gate-session.json`` (the entire session — there is one
  active gate per doc target),
* ``.sdd-state/review-assessment-staging-<gate_id>.json`` (or the
  legacy ``review-assessment-staging.json`` when the per-gate file is
  absent), and
* appends a ``discarded`` event to the project's reference ledger so the
  audit trail records when the gate was dropped.

Lives in :data:`review.transitions.ENTRY_PHASES` — it is invoked
directly by the operator (or auto-routed off an advisory's
``next_action_command``) rather than reached via graph traversal.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from sdd_core import output, transient_state
from review_quality.gate_session import (
    delete_session,
    read_session,
    session_path,
)

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase


def _append_discard_ledger_event(
    ctx: PhaseContext, gate_id: str, deleted: list[str],
) -> None:
    """Append a ``discarded`` event to the per-target reference ledger.

    Best-effort: a missing ``.sdd-state/`` directory or a read-only
    checkout silently no-ops (mirrors the
    :func:`sdd_core.reference_ledger.append` contract). Keeps the audit
    trail aligned with the rest of the pipeline's append-only history
    so an operator can reconstruct *when* a gate was discarded without
    consulting external state.
    """
    from sdd_core import reference_ledger
    try:
        reference_ledger.append(
            category=ctx.category,
            target_name=ctx.target_name,
            project_path=ctx.project_path,
            script="review/pipeline-tick.py --phase discard",
            extra={
                "event": "discarded",
                "gate_id": gate_id,
                "deleted": list(deleted),
            },
        )
    except Exception as exc:
        # Discard is operator-driven recovery — telemetry must never block.
        output.warn(f"audit-log append failed: {exc}")


def _delete_staging_files(
    ctx: PhaseContext, gate_id: str,
) -> list[str]:
    """Delete per-gate + legacy staging files; return the deleted paths.

    The per-gate filename is the canonical shape; the legacy
    (``review-assessment-staging.json``) sibling is also unlinked when
    present so a workflow that produced the legacy shape under an
    earlier release does not leak state past the discard.
    """
    state_dir = transient_state.state_dir(
        ctx.category, ctx.target_name, ctx.project_path,
    )
    deleted: list[str] = []
    candidates = [
        os.path.join(state_dir, transient_state.staging_filename(gate_id)),
        os.path.join(state_dir, transient_state.STAGING_FILENAME),
    ]
    for path in candidates:
        try:
            os.unlink(path)
            deleted.append(path)
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return deleted


def handle_discard(args: argparse.Namespace) -> None:
    """Discard the named gate's session + staging state.

    The handler reads the existing gate session once. Three outcomes:

    * **No session on disk.** Nothing to discard — emit a structured
      ``no_op`` envelope so the caller can distinguish "already clean"
      from a real delete.
    * **gate_id matches.** Delete the gate-session file, the per-gate
      staging file (and any legacy sibling), and append a ``discarded``
      ledger event.
    * **gate_id mismatch.** Preserve all state. Surface the recorded
      ``preserved_gate_id`` so the operator can re-issue the discard
      with the correct flag, or pivot to an alternate recovery.
    """
    ctx = PhaseContext.from_args(args)
    requested_gate_id = (getattr(args, "gate_id", None) or "").strip()

    if not requested_gate_id:
        output.error(
            "discard: --gate-id is required",
            hint=(
                "Provide --gate-id <id> so the discard phase only "
                "deletes session state matching the named gate."
            ),
        )
        return

    gate_session_path = session_path(
        ctx.category, ctx.target_name, ctx.project_path,
    )
    has_session = os.path.isfile(gate_session_path)
    session = read_session(
        ctx.category, ctx.target_name, ctx.project_path,
        quiet_missing=True,
    )
    gate = session.get("review_gate") or {}
    existing_gate_id = (gate.get("gate_id") or "").strip()

    if not has_session:
        output.success(
            {
                "outcome": "no_op",
                "requested_gate_id": requested_gate_id,
                "reason": "no_gate_session_on_disk",
                "deleted": [],
            },
            f"discard: no gate session present for {ctx.target_name!r}",
        )
        return

    if existing_gate_id and existing_gate_id != requested_gate_id:
        output.success(
            {
                "outcome": "preserved",
                "preserved_gate_id": existing_gate_id,
                "requested_gate_id": requested_gate_id,
                "reason": "gate_id_mismatch",
                "deleted": [],
            },
            (
                f"discard: gate_id mismatch — keeping {existing_gate_id!r} "
                f"(requested {requested_gate_id!r})"
            ),
        )
        return

    deleted: list[str] = []
    if delete_session(ctx.category, ctx.target_name, ctx.project_path):
        deleted.append(gate_session_path)
    deleted.extend(_delete_staging_files(ctx, requested_gate_id))

    _append_discard_ledger_event(ctx, requested_gate_id, deleted)

    output.success(
        {
            "outcome": "discarded",
            "discarded_gate_id": requested_gate_id,
            "deleted": deleted,
        },
        f"discard: dropped gate {requested_gate_id!r}",
    )


@dataclass
class DiscardInput(PhaseInput):
    """Typed input for the ``discard`` phase.

    ``gate_id`` rides on the common parent parser (lifecycle flag), so
    only its declaration is needed here for :meth:`Phase._build_input`
    to materialise the field. ``--gate-id`` is required at runtime; the
    handler emits an error envelope when it is omitted.
    """

    parent_todo: str | None = None
    parent_todo_content: str | None = None
    gate_id: str | None = None
    category: str = "spec"
    target_name: str = ""


@phase(
    name="discard",
    emits=frozenset(),
    help="Discard a gate's session + staging state",
    description=__doc__,
)
class DiscardPhase(Phase):
    Input = DiscardInput

    def handle(self, args: argparse.Namespace) -> None:
        handle_discard(args)
