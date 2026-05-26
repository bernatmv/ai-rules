"""Delta-review prompt template + predicates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

__all__ = [
    "DeltaPredicateResult",
    "MAX_DELTA_LINES",
    "delta_eligible",
    "facets_to_review",
    "build_delta_prompt",
    "FACET_TO_SECTION_MAP",
]

MAX_DELTA_LINES = 10


# Section names → facets (per-document section). Adding a new doc type
# extends this mapping without touching the launch handler.
FACET_TO_SECTION_MAP: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "requirements": (
        ("Introduction", ("intent_clarity",)),
        ("Alignment with Product Vision", ("alignment",)),
        ("Requirements", ("requirement_quality", "acceptance_criteria")),
        ("Non-Functional Requirements", ("nfr_coverage",)),
        ("Cross-Repo Scope", ("cross_repo_scope",)),
    ),
    "design": (
        ("Overview", ("scope",)),
        ("Architecture", ("architecture_quality",)),
        ("Components", ("component_design",)),
        ("Data Models", ("data_modeling",)),
        ("Error Handling", ("error_handling",)),
        ("Testing Strategy", ("testing_strategy",)),
    ),
    "tasks": (
        ("Tasks", ("task_decomposition", "task_traceability")),
    ),
}


@dataclass(frozen=True)
class DeltaPredicateResult:
    eligible: bool
    miss_reason: "str | None"


def delta_eligible(
    *,
    changed_lines: int,
    structural_changes: bool,
    prior_quality_present: bool,
) -> DeltaPredicateResult:
    """True iff the most recent edit qualifies for a delta-mode review.

    Three predicates, each with a stable miss reason so callers can emit
    ``output.info`` naming the predicate that fired.
    """
    if not prior_quality_present:
        return DeltaPredicateResult(False, "no_prior_quality_artifact")
    if structural_changes:
        return DeltaPredicateResult(False, "h2_structural_change")
    if changed_lines <= 0:
        return DeltaPredicateResult(False, "no_changed_lines")
    if changed_lines > MAX_DELTA_LINES:
        return DeltaPredicateResult(False, f"changed_lines_above_{MAX_DELTA_LINES}")
    return DeltaPredicateResult(True, None)


def facets_to_review(
    doc_type: str, touched_sections: Iterable[str],
) -> list[str]:
    """Return the facets that should be re-reviewed given the touched
    sections. Unknown doc types or sections fall back to an empty list
    so the caller routes back to full review.
    """
    mapping = dict(FACET_TO_SECTION_MAP.get(doc_type, ()))
    facets: list[str] = []
    seen: set[str] = set()
    for section in touched_sections:
        for facet in mapping.get(section, ()):
            if facet not in seen:
                facets.append(facet)
                seen.add(facet)
    return facets


def build_delta_prompt(
    *,
    doc_name: str,
    diff: str,
    facets: list[str],
    prior_overall_status: str = "",
) -> str:
    """Assemble the delta-review prompt body.

    The agent receives only the diff plus the facet list, so the
    response stays scoped — `update-quality.py --delta-merge` then
    folds the per-facet scores back into the prior artifact.
    """
    facet_lines = "\n".join(f"  - {f}" for f in facets) or "  (none — fall back to full review)"
    prior_line = (
        f"Prior overall_status: {prior_overall_status}." if prior_overall_status else ""
    )
    return (
        f"# Delta review for {doc_name}\n\n"
        f"{prior_line}\n\n"
        f"Re-evaluate ONLY the facets below against the diff that follows.\n"
        f"Other facets keep their prior pass status.\n\n"
        f"## Facets in scope\n{facet_lines}\n\n"
        f"## Diff\n```\n{diff}\n```\n"
    )
