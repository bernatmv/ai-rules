"""Pipeline launch phase: orchestrate review session setup and sub-agent dispatch.

Re-exports the public surface that consumers reference via
``review.pipeline_phases.launch``. The orchestrator + dataclasses live
in :mod:`.phase`; helpers in :mod:`.preconditions`, :mod:`.prompt`,
:mod:`.session_setup`, and :mod:`.result_assembly`.
"""
from __future__ import annotations

# Test-mock targets reference the legacy module-level name
# ``review.pipeline_phases.launch.read_session`` /
# ``...get_phase_snapshot``; preserve the import here so existing
# patches keep resolving.
from review_quality.gate_session import (  # noqa: F401
    get_phase_snapshot,
    read_session,
)

from .dataclass import LaunchInput, LaunchPhase  # noqa: F401

# Pin ``LaunchPhase.__module__`` to the package module so the phase
# registry contract (every registered class lives in a module discovered
# by the side-effect import loop) holds — the loop walks file siblings,
# not sub-package members, so ``launch`` is the discoverable name.
LaunchPhase.__module__ = __name__
from .phase import (  # noqa: F401
    POST_FIX_USER_CHOICES_SOURCE_LAUNCH,
    POST_FIX_USER_CHOICES_SOURCE_POST_REVIEW,
    _handle_launch,
)
from .preconditions import (  # noqa: F401
    _doc_list_contains_requirements,
    _resolve_review_type,
    _run_launch_preconditions,
    _run_requirements_pre_check,
)
from .prompt import (  # noqa: F401
    PROGRESS_CHECKLIST_KEY,
    PROMPT_CHANGE_DOC_CHANGED,
    PROMPT_CHANGE_PROMPT_CHANGED,
    PROMPT_CHANGE_UNCHANGED,
    _apply_post_review_substitutions,
    _build_gate_prompt,
    _classify_prompt_change,
    _compute_doc_list_sha,
    canonicalise_sub_agent_prompt,
    sub_agent_prompt_sha256,
)
from .result_assembly import (  # noqa: F401
    OUTCOME_PRECONDITIONS_UNMET,
    OUTCOME_READY,
)
from .session_setup import (  # noqa: F401
    _launch_time_post_fix_user_choices,
)

# Mirror the original module's ``_WORKFLOW_MODES`` re-export so tests
# importing it from ``review.pipeline_phases.launch`` keep resolving.
from review_quality.constants import WORKFLOW_MODES as _WORKFLOW_MODES  # noqa: F401
