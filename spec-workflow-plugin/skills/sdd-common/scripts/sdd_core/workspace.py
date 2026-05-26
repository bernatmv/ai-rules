"""Workspace coordination — public API surface.

Unified import surface for workspace coordination. Consumers import
``from sdd_core import workspace`` and reach every manifest, tracker,
approval, phase, and query helper without knowing which sub-module
implements each one.

Sub-modules:

- workspace_manifest: ManifestData, ManifestRepo, ManifestWorkflow,
                      read/write/require/validate_manifest,
                      get_coordinator, get_target_repos
- workspace_tracker:  TrackerData, DocApprovals, DocStatusMap,
                      TrackerSubSpec, TrackerSummary,
                      read/write/require_tracker,
                      update_sub_spec_status, update_doc_approval,
                      calculate_summary, finalize_and_save
- workspace_approval: collect_pending_subspecs, apply_batch_approval,
                      collect_phase_pending, apply_phase_approval,
                      create_pending_batch, read_pending_batch,
                      cleanup_pending_batch
- workspace_phase:    get_current_phase, set_current_phase,
                      advance_phase, advance_with_gate,
                      is_phase_complete,
                      update_doc_status, record_phase_gate,
                      repos_eligible_for_phase, init_doc_status
- workspace_query:    active_repos, filter_by_doc_status,
                      repos_needing_work, phase_progress_summary,
                      build_workspace_status

**Maintenance:** ``__all__`` below must stay in sync with the sub-module
``__all__`` lists.  ``TestFacadeAllSync`` in ``test_workspace.py`` enforces
this — a CI failure means a new export was added to a sub-module without
updating this list.
"""
from .workspace_manifest import *   # noqa: F401,F403
from .workspace_tracker import *    # noqa: F401,F403
from .workspace_approval import *   # noqa: F401,F403
from .workspace_phase import *      # noqa: F401,F403
from .workspace_query import *      # noqa: F401,F403

__all__ = [
    "WorkspaceCallContext",
    "is_workspace_context",
    # workspace_manifest
    "ManifestRepo",
    "ManifestWorkflow",
    "ManifestData",
    "VALID_MANIFEST_STATUSES",
    "VALID_WORKFLOW_MODES",
    "VALID_REPO_TYPES",
    "MANIFEST_SCHEMA_VERSION",
    "REPO_ID_REGEX",
    "BOOTSTRAP_PRISTINE_TTL_SECONDS",
    "BootstrapFreshness",
    "validate_repo_id",
    "bootstrap_freshness",
    "read_manifest",
    "write_manifest",
    "require_manifest",
    "validate_manifest",
    "get_coordinator",
    "get_target_repos",
    "write_initial_manifest",
    "manifest_repos_match",
    # workspace_tracker
    "VALID_TRANSITIONS",
    "VALID_APPROVAL_TRANSITIONS",
    "VALID_APPROVAL_STATUSES",
    "VALID_STATUSES",
    "TRACKER_SCHEMA_VERSION",
    "DOC_NAMES",
    "SubSpecStatus",
    "ApprovalDocStatus",
    "WorkspaceStatus",
    "DocApprovalRecord",
    "DocApprovals",
    "DocStatusMap",
    "TrackerSubSpec",
    "TrackerSummary",
    "PhaseStatusCounts",
    "ByPhaseSummary",
    "PhaseGateRecord",
    "PhaseGates",
    "WorkflowConfig",
    "TrackerData",
    "SubSpecUpdate",
    "PollResult",
    "TrackerReadResult",
    "read_tracker",
    "read_tracker_quiet",
    "write_tracker",
    "require_tracker",
    "create_default_tracker",
    "is_v2",
    "update_sub_spec_status",
    "update_doc_approval",
    "calculate_summary",
    "derive_workspace_status",
    "finalize_and_save",
    "poll_sub_spec_status",
    "write_initial_tracker",
    "tracker_repos_match",
    "mark_review_retroactive",
    "TrackerUpdateOutcome",
    "update_tracker_or_advisory",
    "iter_workspace_repo_roots",
    # workspace_approval
    "BatchApprovalResult",
    "PhaseApprovalResult",
    "collect_pending_subspecs",
    "require_pending_subspecs",
    "generate_approval_summary",
    "apply_batch_approval",
    "collect_phase_pending",
    "generate_phase_approval_summary",
    "apply_phase_approval",
    "create_pending_batch",
    "read_pending_batch",
    "cleanup_pending_batch",
    # workspace_phase
    "DOC_PHASES",
    "PHASE_ORDER",
    "PHASE_COMPLETE",
    "DOC_STATUS_TRANSITIONS",
    "VALID_DOC_STATUSES",
    "PHASE_STATUS_MAP",
    "get_current_phase",
    "set_current_phase",
    "advance_phase",
    "advance_with_gate",
    "is_phase_complete",
    "update_doc_status",
    "record_phase_gate",
    "record_phase_history",
    "repos_eligible_for_phase",
    "init_doc_status",
    # workspace_query
    "active_repos",
    "filter_by_doc_status",
    "all_active_at_doc_status",
    "repos_needing_work",
    "phase_progress_summary",
    "categorize_repos_by_doc_status",
    "build_workspace_status",
]
