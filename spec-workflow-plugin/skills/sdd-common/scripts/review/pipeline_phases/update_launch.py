"""Update-mode launch phase — emits the binding checklist for Steps 4 / 6 / 7.1 / 8.

Peer of :mod:`pipeline_phases.launch` for the creation-mode flow.
Differences:

* ``progress_checklist_key`` defaults to ``update-mode.default.v1``.
* Doc list is mandatory (creation-mode launch synthesises it from
  the checklist key; update-mode requires the agent to declare which
  docs were edited so the binding gate sequence is precise).
* ``next_action_command`` chain points at:
  Step 4 → ``review/count-effective-lines.py``,
  Step 6 → ``util/generate-prompt.py --type review-action``,
  Step 7.1 → ``review/pipeline-tick.py --phase pre-approval``,
  Step 8 → ``approval/request.py``.

Registered through the existing :func:`review.phase_kit.phase`
decorator so the dispatcher's ``_accepted_flags`` reflection picks
up the new phase without a parallel table.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Optional

from sdd_core import output
from sdd_core import preflight_state
from sdd_core.command_templates import (
    build_approval_formal_prompt_command,
    build_review_action_prompt_command,
    build_review_update_quality_command,
)
from review_quality.constants import DEFAULT_REVIEW_SCOPE

from ..phase_kit import Phase, PhaseContext, PhaseInput, phase
from .commands import build_phase_cmd
from .constants import PHASE_PRE_APPROVAL


PROGRESS_CHECKLIST_KEY = "update-mode.default.v1"

_PROGRESS_CHECKLIST = (
    "## Update-Mode Gate Checklist\n"
    "\n"
    "- [ ] Step 4: Validate edited docs (size + structural checks)\n"
    "- [ ] Step 6: Present changes via review-action prompt\n"
    "- [ ] Step 7.1: Run pre-approval gate (MANDATORY)\n"
    "- [ ] Step 8: Approve via approval/request.py + update-status.py\n"
    "\n"
    "Copy this checklist into your notes to track progress.\n"
    "Phase commands are MANDATORY — do NOT call underlying scripts directly."
)


# Step-id suffixes the binding gate sequence owns. A new step is a
# tuple edit + a matching ``_OWNED_TODO_LABELS`` entry; the helpers
# below stay pure projections.
_OWNED_TODO_STEP_SUFFIXES: Final[tuple[str, ...]] = (
    "step-4-validate",
    "step-6-present",
    "step-7-1-pre-approval",
    "step-8-approve",
)

_OWNED_TODO_LABELS: Final[dict[str, str]] = {
    "step-4-validate": "Validate edited docs",
    "step-6-present": "Present changes (review-action)",
    "step-7-1-pre-approval": "Pre-approval gate",
    "step-8-approve": "Approve via approval/request.py",
}


def _present_changes_command(doc: str) -> str:
    """Canonical Step 6 invocation for the update-mode checklist."""
    return build_review_action_prompt_command(doc=doc)


def _build_owned_todo_ids(parent_todo: str) -> list[str]:
    """Return the four step-id TODOs the gate sequence binds.

    Naming mirrors the agent-visible step labels in
    ``update-mode-workflow.md`` so the agent's TodoWrite payload reads
    the same rows the prose advertises. Silently skipping any step
    replays the missed call at the next tick.
    """
    base = parent_todo or "update"
    return [f"{base}-{suffix}" for suffix in _OWNED_TODO_STEP_SUFFIXES]


def _build_todo_payload(parent_todo: str, owned_ids: list[str]) -> dict:
    """Render the TodoWrite payload that binds Steps 4 / 6 / 7.1 / 8."""
    todos = [
        {"id": parent_todo, "content": "Update mode: drive gate sequence",
         "status": "in_progress"},
    ]
    todos.extend(
        {"id": owned_id, "content": _OWNED_TODO_LABELS[suffix],
         "status": "pending"}
        for suffix, owned_id in zip(_OWNED_TODO_STEP_SUFFIXES, owned_ids)
    )
    return {"todos": todos, "merge": True}


def _handle_update_launch(ctx: PhaseContext, inp: "UpdateLaunchInput") -> None:
    """Emit the update-mode binding envelope.

    Returns the same top-level keys the creation-mode launch emits so
    consumer contracts (TodoWrite payload, ``phase_commands``,
    ``next_action_command`` chain) are byte-identical from the agent's
    perspective.
    """
    doc_list = inp.doc_list or ""
    docs = [d.strip() for d in doc_list.split(",") if d.strip()]
    primary_doc = docs[0] if docs else "<doc>"

    parent_todo = ctx.parent_todo or inp.parent_todo or "update"
    gate_id = ctx.gate_id or inp.gate_id or "default"
    lifecycle_flags = f" --parent-todo {parent_todo} --gate-id {gate_id}"

    pre_approval_cmd = build_phase_cmd(
        PHASE_PRE_APPROVAL,
        project_path=ctx.project_path or ".",
        category=ctx.category,
        target_name=ctx.target_name,
        extra_args=f'--doc-list "{doc_list}"',
        lifecycle_flags=lifecycle_flags,
    )

    phase_commands = {
        "present_changes": _present_changes_command(primary_doc),
        "pre_approval": pre_approval_cmd,
        "approval_request": build_approval_formal_prompt_command(
            doc_list=doc_list,
        ),
        "update_quality": build_review_update_quality_command(
            target=ctx.target_name or ctx.category,
            category=ctx.category,
        ),
    }

    owned_ids = _build_owned_todo_ids(parent_todo)
    todo_payload = _build_todo_payload(parent_todo, owned_ids)

    next_action_command = phase_commands["present_changes"]

    result = {
        "category": ctx.category,
        "target_name": ctx.target_name,
        "doc_list": doc_list,
        "review_skill": inp.review_skill,
        "scope": inp.scope,
        "workflow_mode": inp.workflow_mode,
        "progress_checklist_key": PROGRESS_CHECKLIST_KEY,
        "progress_checklist": _PROGRESS_CHECKLIST,
        "owned_todo_ids": owned_ids,
        "phase_commands": phase_commands,
        "todo_write_payload": todo_payload,
        "next_action_command": next_action_command,
        "next_action_command_note": (
            "Run phase_commands in order: present_changes → pre_approval → "
            "approval_request. phase_commands.update_quality refreshes "
            "review-quality.json after edits land."
        ),
        "pending_calls": [],
    }
    preflight_state.mark_resolved(
        "unstaged_spec_edits_without_approval",
        workspace=ctx.project_path or ".",
    )

    output.success(
        result,
        f"Update-mode launch ready for {ctx.target_name or ctx.category} "
        f"({len(docs)} doc(s))",
    )


@dataclass
class UpdateLaunchInput(PhaseInput):
    """Typed input for the ``update-launch`` phase."""

    doc_list: str = field(
        default=None, metadata={"help": "Comma-separated document list"},
    )
    review_skill: str = field(
        default="", metadata={"help": "Review skill name for parity with launch"},
    )
    scope: str = field(
        default=DEFAULT_REVIEW_SCOPE,
        metadata={"help": "Review scope for parity with launch"},
    )
    workflow_mode: str = field(
        default="update", metadata={
            "help": "Workflow mode (default: update)",
            "choices": ("update", "create", "resume"),
        },
    )
    parent_todo: Optional[str] = None
    gate_id: Optional[str] = None
    category: str = "spec"
    target_name: str = ""


@phase(
    name="update-launch",
    emits=frozenset(),
    help="Emit the binding checklist for update-mode Steps 4 / 6 / 7.1 / 8",
    description=__doc__,
)
class UpdateLaunchPhase(Phase):
    """Update-mode entry — emits the binding checklist envelope.

    Standalone entry phase (not on the review graph). Listed under
    :data:`review.transitions.ENTRY_PHASES` so the registry parity
    check tolerates its presence.
    """

    Input = UpdateLaunchInput

    def handle(self, ctx: PhaseContext, inp: UpdateLaunchInput) -> None:
        _handle_update_launch(ctx, inp)
