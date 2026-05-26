"""Launch phase typed input + Phase registration.

:class:`LaunchInput` reflects onto argparse via :class:`Phase` so the
review skill, doc list, scope, workflow mode, and fix-cycle cap are
all surfaced as CLI flags. :class:`LaunchPhase` is the registered
phase entry point — :meth:`LaunchPhase.handle` delegates to
:func:`._handle_launch` in :mod:`.phase`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from review_quality.constants import (
    DEFAULT_MAX_FIX_CYCLES,
    REVIEW_SCOPES,
    SCOPE_PER_DOCUMENT,
    WORKFLOW_MODES as _WORKFLOW_MODES,
)

from ...phase_kit import Phase, PhaseContext, PhaseInput, phase
from ..common_validators import (
    require_launch_target_name as _require_launch_target_name,
    require_parent_todo_pair as _require_parent_todo_pair,
)
from ..constants import PHASE_POST_REVIEW


@dataclass
class LaunchInput(PhaseInput):
    """Typed input for the ``launch`` phase.

    XOR-pairing and target-name invariants live on
    :meth:`__post_init__`. Lifecycle fields (``parent_todo`` /
    ``gate_id`` / ``category`` / ``target_name``) mirror the common
    parent parser; :meth:`Phase._attach_input_flags` skips them when
    reflecting the dataclass onto argparse so the agent-facing CLI
    exposes each flag exactly once.
    """

    review_skill: str = field(
        default=None, metadata={
            "help": "Review skill name (e.g. sdd-review-spec-docs)",
        },
    )
    doc_list: str = field(
        default=None, metadata={"help": "Comma-separated document list"},
    )
    scope: str = field(
        default=SCOPE_PER_DOCUMENT, metadata={
            "help": "Pipeline scope",
            "choices": REVIEW_SCOPES,
        },
    )
    workflow_mode: str = field(
        default="resume", metadata={
            "help": (
                "Workflow mode: create (fresh), update (targeted edit), "
                "resume (continue)"
            ),
            "choices": _WORKFLOW_MODES,
        },
    )
    max_fix_cycles: int = field(
        default=DEFAULT_MAX_FIX_CYCLES, metadata={
            "help": "Max fix-then-re-review cycles",
        },
    )
    confirm_continuation: bool = field(
        default=False, metadata={
            "help": (
                "Consume the single-document stop marker and proceed "
                "past the continuation gate."
            ),
        },
    )
    parent_todo: Optional[str] = None
    parent_todo_content: Optional[str] = None
    gate_id: Optional[str] = None
    category: str = "spec"
    target_name: str = ""

    def __post_init__(self) -> None:
        """Enforce the XOR-pairing and spec / discovery target-name
        invariants on construction. Raises ``ValueError`` — the
        :class:`Phase` base catches it at dispatch time and re-emits
        via :func:`sdd_core.output.error`.
        """
        _require_parent_todo_pair(self.parent_todo, self.gate_id)
        _require_launch_target_name(self.category, self.target_name)

    def validate_for_phase(self) -> "list[str]":
        """Phase-time precondition gate. Surfaces missing
        ``--review-skill`` / ``--doc-list`` flags as a typed recoverable
        miss instead of an ``AttributeError`` deep inside
        ``_resolve_review_type`` / ``doc_list.split(',')``.

        Each problem string is operator-readable and mentions the
        canonical recovery (the helpful ``--review-skill`` enumeration
        and the ``--doc-list`` shape). The dispatcher pairs the list
        with a runnable ``next_action_command_sequence``, so a
        missing-flag launch turns into one clean retry literal.
        """
        from sdd_core.review_skills import ReviewSkill

        problems: list[str] = []
        if not self.review_skill:
            problems.append(
                "--review-skill is required; expected one of "
                f"{sorted(s.value for s in ReviewSkill)}"
            )
        if not self.doc_list:
            problems.append(
                "--doc-list is required; expected a comma-separated "
                "list (e.g., 'requirements.md,design.md,tasks.md')"
            )
        return problems


@phase(
    name="launch",
    emits=frozenset({PHASE_POST_REVIEW}),
    help="Generate sub-agent prompt and all review commands",
    description=(
        "Pipeline launch phase: orchestrate review session setup and "
        "sub-agent dispatch."
    ),
)
class LaunchPhase(Phase):
    """Launch — the entry to the review graph. Initialises the gate
    session, resolves the review skill and doc list, emits the
    sub-agent prompt, and advances ``required_next_phase`` to
    ``post-review``.
    """

    Input = LaunchInput

    def handle(self, ctx: PhaseContext, inp: LaunchInput) -> None:
        from .phase import _handle_launch
        _handle_launch(ctx, inp)
