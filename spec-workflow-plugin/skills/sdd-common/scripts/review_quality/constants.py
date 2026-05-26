"""Pure data constants shared across review_quality modules.

Extracted to break circular dependencies. No query functions or I/O here.
"""
from __future__ import annotations

import re

from sdd_core.doc_config import DOCUMENT_REGISTRY  # canonical source

SCHEMA_VERSION = "3.0.0"

SCORE_VALUE_MAP = {"pass": 1.0, "partial": 0.5, "fail": 0.0, "na": None}

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Keys that are script-owned — strip silently if AI includes them in input
_SCRIPT_OWNED_KEYS = frozenset({
    "history", "schema_version", "generated_at", "last_full_review_at",
    "overall_score", "overall_status", "documents",
})

_STEERING_SIZE_LIMIT = 200

VALID_FINDING_TYPES = frozenset({
    "conflict", "duplication", "gap", "drift",
    # Advisory cross-doc finding surfaced at per-document scope; does
    # not route into the fix loop. Merged into candidate pair rows at
    # the next final-scope review (see :mod:`review_quality.cross_validation`).
    "advisory_cross_validation",
})

VALID_THOROUGHNESS_RATINGS = frozenset({"Comprehensive", "Adequate", "Basic", "Insufficient"})

VALID_SPEC_TYPES = frozenset({"standard", "bug-fix"})

VALID_CONFIDENCE_LEVELS = frozenset({"HIGH", "MEDIUM", "LOW"})
PASSING_CONFIDENCE_LEVELS = frozenset({"HIGH", "MEDIUM"})

DESIGN_PRINCIPLE_WEIGHT = {"HIGH": 2, "MEDIUM": 1, "LOW": 0, "N/A": None}

PASS_THRESHOLD_PCT = 80
NEEDS_WORK_THRESHOLD_PCT = 60
DOC_STATUS_THRESHOLDS = {
    "fail_below": NEEDS_WORK_THRESHOLD_PCT / 100,
    "pass_at_or_above": PASS_THRESHOLD_PCT / 100,
}

CV_DEDUCTION_PER_FINDING = 0.5
CV_MAX_DEDUCTION = 1.5

STRUCTURAL_NA_PREFIX = "structural-na:"

DEFAULT_GATE_ID = "default"
INITIAL_FIX_CYCLE = 1

PROGRESS_SCHEMA_VERSION = "1.0.0"
MIN_CHECKS_CITED = 1

MIN_REPORT_COLUMNS = 3
REPORT_SCORE_COL = 1
REPORT_EVIDENCE_COL = -1

# Git history checks (e.g. detect-doc-state.py) should complete quickly since
# they query the local repo only. 5 seconds covers slow disk I/O or large repos
# without blocking the agent indefinitely on a hung git process.
GIT_TIMEOUT_SECS = 5


def empty_issues() -> dict[str, int]:
    """Return a fresh empty-issues dict (no .copy() needed)."""
    return {"critical": 0, "warning": 0, "suggestion": 0}


def empty_score() -> dict[str, int | float]:
    """Return a fresh empty-score dict (no .copy() needed)."""
    return {"value": 0, "max": 0, "percent": 0}


TIER1_SCRIPT_SPECS = {
    "spec/lint-tasks.py": {
        "doc_args": ["tasks_md"],
        "covers": [
            "task_lifecycle_suffix_valid",
            "implementation_prompts_structured",
        ],
    },
    "spec/check-traceability.py": {
        "doc_args": ["requirements_md", "tasks_md"],
        "covers": ["requirements_traceability_complete"],
        "attribution_doc": "tasks_md",
    },
    "prd/validate-prd.py": {
        "doc_args": ["prd_md"],
        "covers": [
            "requirements_when_then_format",
            "nfrs_all_categories_specific",
            "open_questions_have_owners",
            "alternatives_considered_present",
            "rollout_plan_with_gates",
            "goals_table_complete",
        ],
    },
    # Lint-shaped tier1 spec: runs via internal_lints.import_paths_resolve
    # (project-wide scan, not per-doc) so it omits ``doc_args``. The
    # tier1 runner skips entries without ``doc_args`` — actual scoring
    # lives in the lint aggregator.
    "import-paths-resolve": {
        "script": "internal_lints/import_paths_resolve.py",
        "covers": ["import_paths_resolve"],
    },
}


# Why: when a Tier-1 facet renders as ``na`` in the per-doc gate
# prompt, the sub-agent surfaces an inline scope explanation so the
# reader knows why the facet does not apply (e.g. design.md does not
# carry tasks, so ``task_lifecycle_suffix_valid`` is na for that doc).
# Single source of truth — every facet ID present in a
# :data:`TIER1_SCRIPT_SPECS` ``covers`` list must have a matching
# label here. The CI guard in
# ``tests/test_sub_agent_prompt_renders_na_scope.py`` enforces it.
DEFAULT_TIER1_NA_SCOPE_LABEL = "out of scope for this gate"

TIER1_FACET_SCOPE_LABELS: dict[str, str] = {
    "task_lifecycle_suffix_valid": "applies only when tasks.md is in the gate's doc set",
    "implementation_prompts_structured": "applies only when tasks.md is in the gate's doc set",
    "requirements_traceability_complete": (
        "applies only when both requirements.md and tasks.md are in the gate's doc set"
    ),
    "requirements_when_then_format": "applies only when prd.md is in the gate's doc set",
    "nfrs_all_categories_specific": "applies only when prd.md is in the gate's doc set",
    "open_questions_have_owners": "applies only when prd.md is in the gate's doc set",
    "alternatives_considered_present": "applies only when prd.md is in the gate's doc set",
    "rollout_plan_with_gates": "applies only when prd.md is in the gate's doc set",
    "goals_table_complete": "applies only when prd.md is in the gate's doc set",
    "import_paths_resolve": "project-wide lint; rendered na when scope excludes import-path checks",
}


def _validate_tier1_completeness() -> None:
    for rtype, reg in DOCUMENT_REGISTRY.items():
        for script in reg.get("tier1_scripts", []):
            if script not in TIER1_SCRIPT_SPECS:
                raise ValueError(
                    f"DOCUMENT_REGISTRY['{rtype}']['tier1_scripts'] lists "
                    f"'{script}' but TIER1_SCRIPT_SPECS has no entry for it"
                )


_validate_tier1_completeness()


class TodoStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class GateState:
    """Gate lifecycle states for the review pipeline state machine."""
    FIX = "FIX"
    PRESENT = "PRESENT"
    RE_VALIDATE = "RE_VALIDATE"
    RE_REVIEW = "RE_REVIEW"
    REVIEW_COMPLETE = "REVIEW_COMPLETE"
    MAX_CYCLES_EXHAUSTED = "MAX_CYCLES_EXHAUSTED"
    NEEDS_WORK = "NEEDS_WORK"
    PASS = "PASS"

# Intermediate states that indicate a stale/interrupted session
STALE_INTERMEDIATE_STATES = frozenset({
    GateState.FIX, GateState.RE_VALIDATE,
    GateState.PRESENT, GateState.RE_REVIEW,
    GateState.REVIEW_COMPLETE,
})


# Default fix cycle limit: one fix pass + one re-review. Kept at 2 so
# the agent cannot grind indefinitely on a review gate — empirically
# tuned (see Review Gate tuning notes).
DEFAULT_MAX_FIX_CYCLES = 2

# Review scope vocabulary — single source of truth consumed by
# ``review_quality.scoring``, ``sdd_core.prompts``, and the
# ``review/update-quality.py`` argparse. Adding a new scope is one
# constant + one row in :data:`REVIEW_SCOPES`.
SCOPE_PER_DOCUMENT = "per-document"
SCOPE_FINAL = "final"
REVIEW_SCOPES: tuple[str, ...] = (SCOPE_PER_DOCUMENT, SCOPE_FINAL)

DEFAULT_REVIEW_SCOPE = SCOPE_PER_DOCUMENT

# Canonical ``--user-choice`` vocabulary surfaced on ``post-review``
# envelopes and enforced by ``post-fix.py``'s argparse. Single source
# of truth — consumers pick from the emitted list instead of
# hard-coding.
USER_CHOICE_ALLOWED: tuple[str, ...] = (
    "accept", "fix_all", "fix_selected", "fix_critical",
    "fix_all_in_doc_first", "defer_to_external_workflow",
    "proceed", "re_review", "skip",
)

# Recommended-choice constants emitted on ``phase_commands.post_fix.user_choice_recommended``.
# Members of :data:`USER_CHOICE_ALLOWED`; named separately so the
# default-recommendation policy reads as named constants rather than
# magic strings.
RECOMMENDED_CHOICE_ACCEPT: str = "accept"
RECOMMENDED_CHOICE_FIX_ALL: str = "fix_all"
RECOMMENDED_CHOICE_PROCEED: str = "proceed"
# Recommended when every actionable finding is rooted outside the
# reviewed doc — the operator runs the linked external workflow and
# the gate advances without consuming a fix-cycle slot.
RECOMMENDED_CHOICE_DEFER_EXTERNAL: str = "defer_to_external_workflow"
# Recommended when actionable findings split between in-doc and
# external root causes — fix the in-doc subset first, surface the
# remainder for the external workflow.
RECOMMENDED_CHOICE_FIX_ALL_IN_DOC_FIRST: str = "fix_all_in_doc_first"

# Sentinel value for ``--user-choice recommended`` — keeps the
# recommended verb a single shared constant rather than a literal that
# argparse and the resolver each spell separately. The resolver
# translates the sentinel into one of :data:`USER_CHOICE_ALLOWED`
# before the rest of the pipeline sees it.
USER_CHOICE_RECOMMENDED_SENTINEL: str = "recommended"

# Workflow modes — ``create`` (greenfield), ``resume`` (continue an open
# gate), ``update`` (in-place refresh on shipped artifacts). Single
# source of truth consumed by every Phase Input dataclass and the
# launch / post-fix builders so the vocabulary stays aligned across
# the dispatch surface.
WORKFLOW_MODES: tuple[str, ...] = ("create", "resume", "update")


# Operator-facing review status string. PASS / PASS_WITH_ADVISORIES /
# NEEDS_WORK are derived from the (actionable, advisory) counter pair via
# :func:`STATUS_FROM_COUNTS`. FAIL is caller-determined — driven by
# critical-finding gates, not counter math — so the function ignores it.
STATUS_PASS: str = "PASS"
STATUS_PASS_WITH_ADVISORIES: str = "PASS_WITH_ADVISORIES"
STATUS_NEEDS_WORK: str = "NEEDS_WORK"
STATUS_FAIL: str = "FAIL"


def STATUS_FROM_COUNTS(*, actionable: int, advisory: int) -> str:
    """Single dispatch from the counter tuple to the status string.

    Invariants:
      * ``PASS``                 ⇔ ``actionable == 0 and advisory == 0``
      * ``PASS_WITH_ADVISORIES`` ⇔ ``actionable == 0 and advisory > 0``
      * ``NEEDS_WORK``           ⇔ ``actionable > 0`` (advisory ignored
                                     for routing — actionable findings
                                     dominate)
      * ``FAIL``                  caller-determined (e.g. critical
                                     findings); not derivable from
                                     counts alone

    The counter pair is the single source of truth for the status the
    operator reads. Any emit site that derives ``status`` from a
    different input drifts — route through this function instead.
    """
    if actionable < 0 or advisory < 0:
        raise ValueError(
            f"counts must be non-negative; got actionable={actionable}, "
            f"advisory={advisory}"
        )
    if actionable == 0 and advisory == 0:
        return STATUS_PASS
    if actionable == 0 and advisory > 0:
        return STATUS_PASS_WITH_ADVISORIES
    return STATUS_NEEDS_WORK

# Set of operator-facing review-status strings that map to a passing
# verdict. ``PASS`` is clean; ``PASS_WITH_ADVISORIES`` is clean for
# routing purposes (advisories surface but do not gate). Used by every
# emit site that needs to ask "is this a pass?" without restating the
# membership tuple.
_PASS_TOKENS: frozenset[str] = frozenset(
    {STATUS_PASS, STATUS_PASS_WITH_ADVISORIES},
)

# User-choice values that advance the cursor past post-fix so a
# subsequent ack-calls round routes forward to check-revalidation
# instead of re-emitting the post-fix command.
CURSOR_ADVANCE_USER_CHOICES: frozenset[str] = frozenset({
    RECOMMENDED_CHOICE_ACCEPT, RECOMMENDED_CHOICE_PROCEED,
    RECOMMENDED_CHOICE_DEFER_EXTERNAL,
})

# Cited-issue status enum used by ``cited_issues_history`` rows.
STATUS_ADDRESSED: str = "addressed"
STATUS_REPLACED: str = "replaced"
STATUS_STILL_OPEN: str = "still_open"
STATUS_OPEN: str = "open"

# Tier 2 facet score enum.
SCORE_FAIL: str = "fail"
SCORE_PARTIAL: str = "partial"
SCORE_PASS: str = "pass"

# Promotion rule names — single source for the rule lookup keys.
RULE_PARTIAL_TO_PASS: str = "partial_to_pass"
RULE_LOOP_BREAKER: str = "loop_breaker"

# Severity ladder used by ``cap_new_issue_severity``; index ordering is
# the comparison rule.
PROMOTION_SEVERITY_ORDER: tuple[str, ...] = (
    "suggestion", "warning", "critical",
)

# Match-kind names used by ``facet_promotion_rules.yaml`` to dispatch
# precondition matchers from the YAML side.
MATCH_KIND_ADDRESSED_COUNT_EQUALS_OPEN: str = "addressed_count_equals_open"
MATCH_KIND_CONSECUTIVE_CYCLES_WITH_NEW: str = "consecutive_cycles_with_new"


def user_choices_for_transition(
    *, scope: str, fix_cycle: int, findings_count: int,
    has_external_state_findings: bool = False,
    has_in_doc_findings: bool = False,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(allowed, excluded)`` for the current transition.

    Single policy surface consumed by ``post-review`` envelope
    emission and ``post-fix`` argparse validation — both read the
    same matrix instead of restating the policy in two places. The
    union of ``allowed`` and ``excluded`` always equals
    :data:`USER_CHOICE_ALLOWED`.

    ``has_external_state_findings`` / ``has_in_doc_findings`` route
    ``defer_to_external_workflow`` and ``fix_all_in_doc_first`` —
    they are excluded when no external-state finding is present
    (defer makes no sense without one) or when no in-doc finding is
    present (split fix has nothing to split).
    """
    excluded: list[str] = []
    if fix_cycle > 0:
        excluded.append("accept")
    if findings_count == 0:
        excluded.extend((
            "fix_all", "fix_selected", "fix_critical",
            "fix_all_in_doc_first", "defer_to_external_workflow",
        ))
    else:
        if not has_external_state_findings:
            excluded.append("defer_to_external_workflow")
        if not (has_external_state_findings and has_in_doc_findings):
            excluded.append("fix_all_in_doc_first")
    if scope == SCOPE_FINAL:
        excluded.append("skip")
    excluded_seen: set[str] = set()
    excluded_unique = [
        c for c in excluded if not (c in excluded_seen or excluded_seen.add(c))
    ]
    allowed = tuple(c for c in USER_CHOICE_ALLOWED if c not in excluded_seen)
    return allowed, tuple(excluded_unique)

REVIEW_QUALITY_FILENAME = "review-quality.json"

# Count of findings surfaced verbatim in the pre-approval summary.
# Above this threshold, the payload switches to a counts-only
# presentation to avoid overwhelming agent-facing output.
MAX_FINDINGS_IN_SUMMARY: int = 3


TODO_NAMESPACES: tuple[str, ...] = ("fix_cycle", "reentry")
TODO_PHASES: tuple[str, ...] = ("apply", "validate", "review")

TODO_CONTENT_TEMPLATES: dict[str, dict[str, str]] = {
    "fix_cycle": {
        "apply": "Fix loop cycle {n}: apply fixes",
        "validate": "Fix loop cycle {n}: validate changes",
        "review": "Fix loop cycle {n}: re-review ({review_scope})",
    },
    "reentry": {
        "apply": "Stale-doc re-review {n}: apply fixes",
        "validate": "Stale-doc re-review {n}: validate changes",
        "review": "Stale-doc re-review {n}: re-review ({review_scope})",
    },
}

TODO_ID_PREFIXES: dict[str, str] = {
    "fix_cycle": "fix-c",
    "reentry": "reentry-r",
}
