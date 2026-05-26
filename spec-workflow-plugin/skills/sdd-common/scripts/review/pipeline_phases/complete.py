"""Pipeline complete phase: clean up gate session after approval."""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import os

from sdd_core import output
from sdd_core.time import ts_now
from review_quality.gate_session import (
    complete_gate, read_session, session_path, write_session,
)
from review_quality.constants import DEFAULT_GATE_ID, SCOPE_PER_DOCUMENT

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from . import SINGLE_DOC_KEYS


def _extract_single_doc_marker(gate: dict, launch_cache: dict) -> dict | None:
    """Return a ``single_doc_stop_marker`` when the just-completed
    gate reviewed exactly one spec document under ``per-document``
    scope — otherwise ``None``.

    The marker lets a subsequent ``--phase launch`` call ask the
    agent (via ``AskQuestion``) whether the early stop was
    intentional, converting a prose-only SKILL.md rule into a
    deterministic gate.
    """
    scope = (
        gate.get("review_scope")
        or launch_cache.get("scope")
        or SCOPE_PER_DOCUMENT
    )
    if scope != SCOPE_PER_DOCUMENT:
        return None
    doc_list_raw = (launch_cache or {}).get("doc_list") or ""
    docs = [d.strip() for d in doc_list_raw.split(",") if d.strip()]
    if len(docs) != 1:
        return None
    doc = docs[0]
    if doc not in SINGLE_DOC_KEYS:
        return None
    return {
        "doc": doc,
        "at": ts_now(),
        "scope": scope,
        "hint": (
            f"Single-document approval recorded for {doc}. Subsequent "
            "--phase launch calls may emit a continuation gate via "
            "`ask_question_payload` so the agent can confirm that the "
            "early stop was intentional (matches the sdd-create-spec "
            "SKILL.md 'single-document request' edge case)."
        ),
    }


def handle_complete(args: argparse.Namespace) -> None:
    """Reset gate session after successful approval.

    ``complete`` is the terminal phase — the approval cleanup has already
    removed ``gate-session.json`` in the common path. Probe the session
    file once here and forward ``quiet_missing=True`` so downstream reads
    don't emit a chorus of "No gate session" INFO lines. The single
    expected-absence banner is emitted at INFO level only, avoiding the
    stderr chorus when the approval hook has already removed the session
    file.
    """
    ctx = PhaseContext.from_args(args)
    category = ctx.category
    target_name = ctx.target_name
    project_path = ctx.project_path

    has_session = os.path.isfile(
        session_path(category, target_name, project_path),
    )
    if not has_session:
        output.info(
            "complete: already cleaned up, no-op"
        )
        output.success(
            {
                "gate_id": DEFAULT_GATE_ID,
                "status": "already_completed",
                "completed_gates": [],
                "terminal": True,
                "no_op": True,
            },
            "Gate session already cleaned up; complete is a no-op",
        )
        return

    session = read_session(
        category, target_name, project_path,
        quiet_missing=True,
    )
    gate = session.get("review_gate") or {}
    gate_id = gate.get("gate_id", DEFAULT_GATE_ID)
    launch_cache = session.get("launch_args_cache") or {}

    marker = _extract_single_doc_marker(gate, launch_cache)

    session = complete_gate(session, gate_id)
    if marker is not None and category == "spec":
        session["single_doc_stop_marker"] = marker
    try:
        write_session(category, target_name, session, project_path)
    except OSError as exc:
        output.error(
            "complete_phase_failed",
            hint=f"Failed to write gate session: {exc}",
            next_action_command="review/pipeline-tick.py --retry",
        )
        return

    payload: dict = {
        "gate_id": gate_id,
        "status": "completed",
        "completed_gates": session.get("completed_gates", []),
        # Single terminator — pipeline-run.py keys on this flag alone
        # to stop ticking.
        "terminal": True,
    }
    if marker is not None:
        payload["single_doc_stop_marker"] = marker
    output.success(payload, f"Gate '{gate_id}' completed — session reset")


@dataclass
class CompleteInput(PhaseInput):
    """Typed input for the ``complete`` phase.

    Lifecycle flags (``category``, ``target_name``, ``project_path``,
    ``parent_todo``, ``gate_id``) live on the common parent parser and
    are omitted here; the ack-flavoured ``complete`` phase keeps the
    XOR-pairing invariant inexpressible by simply not declaring them.
    """


@phase(
    name="complete",
    emits=frozenset(),
    help="Clean up gate session after successful approval",
    description=__doc__,
)
class CompletePhase(Phase):
    """Terminal phase — resets the gate session after an approval.

    Wired through :func:`review.phase_kit.bind_to_prepare_pipeline`
    like every other phase; no function-style ``register`` entry point.
    """

    Input = CompleteInput

    def handle(self, args: argparse.Namespace) -> None:
        handle_complete(args)
