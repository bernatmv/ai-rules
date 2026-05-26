"""Document type registry — single source of truth for document structure.

This module owns the canonical DOCUMENT_REGISTRY data. Both sdd_core modules
(specs, templates) and review_quality modules (registry, builders, validation)
import from here, keeping dependency arrows pointing downward:

    sdd_core.doc_config  ← sdd_core.specs
                         ← sdd_core.templates
                         ← review_quality.registry
"""
from __future__ import annotations

__all__ = [
    "DOCUMENT_REGISTRY",
    "default_doc_list_for_category",
    "expected_headings_for_stem",
    "skill_name_for_category",
]

DOCUMENT_REGISTRY = {
    "steering": {
        "doc_keys": ["product_md", "tech_md", "structure_md"],
        "doc_files": {
            "product_md":   "product.md",
            "tech_md":      "tech.md",
            "structure_md": "structure.md",
        },
        "doc_stems": {
            "product_md":   "product",
            "tech_md":      "tech",
            "structure_md": "structure",
        },
        "expected_headings": {
            "product_md":   ["Product Purpose", "Key Features"],
            "tech_md":      ["Core Technologies", "Development Environment"],
            "structure_md": ["Directory Organization", "Naming Conventions"],
        },
        "cross_validation_pairs": [
            ("product_md", "tech_md"),
            ("product_md", "structure_md"),
            ("tech_md", "structure_md"),
        ],
        "facets": {
            "product_md": [
                {"id": "product_purpose_stated",      "name": "Product Purpose Clearly Stated"},
                {"id": "target_users_described",       "name": "Target Users Accurately Described"},
                {"id": "key_features_comprehensive",   "name": "Key Features Comprehensive"},
                {"id": "business_objectives_aligned",  "name": "Business Objectives Align with Reality"},
                {"id": "success_metrics_measurable",   "name": "Success Metrics Measurable"},
            ],
            "tech_md": [
                {"id": "technology_stack_accurate",          "name": "Technology Stack Accurate"},
                {"id": "architecture_patterns_described",    "name": "Architecture Patterns Correctly Described"},
                {"id": "external_integrations_listed",       "name": "External Integrations Listed"},
                {"id": "performance_requirements_realistic", "name": "Performance Requirements Realistic"},
                {"id": "security_considerations_addressed",  "name": "Security Considerations Addressed"},
                {"id": "import_paths_resolve",                "name": "Import Paths Resolve to Source Tree"},
            ],
            "structure_md": [
                {"id": "directory_structure_matches_codebase", "name": "Directory Structure Matches Codebase"},
                {"id": "naming_conventions_accurate",          "name": "Naming Conventions Accurate"},
                {"id": "import_patterns_documented",           "name": "Import Patterns Correctly Documented"},
                {"id": "module_boundaries_clear",              "name": "Module Boundaries Clear"},
                {"id": "code_organization_reflects_practices", "name": "Code Organization Reflects Practices"},
            ],
        },
        "tier1_scripts":       ["import-paths-resolve"],
        "skill_name":          "sdd-review-steering-docs",
        "comprehension_field": "ai_comprehension_test",
        "extra_doc_fields": {
            "size_check": {"tier1_key": "size_check", "default": "INCOMPLETE"},
        },
    },
    "spec": {
        "doc_keys": ["requirements_md", "design_md", "tasks_md"],
        "optional_doc_keys": ["ui_design_md"],
        "doc_files": {
            "requirements_md": "requirements.md",
            "design_md":       "design.md",
            "tasks_md":        "tasks.md",
            "ui_design_md":    "ui-design.md",
        },
        "doc_stems": {
            "requirements_md": "requirements",
            "design_md":       "design",
            "tasks_md":        "tasks",
            "ui_design_md":    "ui-design",
        },
        "expected_headings": {
            "requirements_md": ["Purpose", "Requirements"],
            "design_md":       ["Design"],
            "tasks_md":        ["Tasks"],
            "ui_design_md":    ["Layout", "Component Inventory", "Interaction Patterns", "Accessibility"],
        },
        "cross_validation_pairs": [
            ("requirements_md", "design_md"),
            ("design_md", "tasks_md"),
            ("requirements_md", "tasks_md"),
        ],
        "cross_validation_pairs_optional": {
            "ui_design_md": [
                ("requirements_md", "ui_design_md"),
                ("ui_design_md", "design_md"),
            ],
        },
        "facets": {
            "requirements_md": [
                {"id": "introduction_clear_context",               "name": "Introduction Provides Clear Context"},
                {"id": "product_vision_alignment",                 "name": "Alignment with Product Vision Documented"},
                {"id": "user_stories_format",                      "name": "User Stories Follow Proper Format"},
                {"id": "acceptance_criteria_testable",             "name": "Acceptance Criteria are Testable"},
                {"id": "nonfunctional_requirements_comprehensive", "name": "Non-Functional Requirements Comprehensive"},
                {"id": "dependency_behavior_parity_explicit",      "name": "Dependency Removals/Behavior Parity Explicit",
                 "structural_na_when": "additive_only_feature"},
            ],
            "design_md": [
                {"id": "steering_alignment_documented",        "name": "Steering Document Alignment Documented"},
                {"id": "code_reuse_analysis_thorough",         "name": "Code Reuse Analysis Thorough"},
                {"id": "architecture_clearly_described",       "name": "Architecture Clearly Described"},
                {"id": "components_interfaces_defined",        "name": "Components and Interfaces Well-Defined"},
                {"id": "error_handling_comprehensive",         "name": "Error Handling Comprehensive"},
                {"id": "testing_strategy_thorough",            "name": "Testing Strategy Thorough"},
                {"id": "dependency_removal_impact_documented", "name": "Dependency Removal Impact Documented",
                 "structural_na_when": "additive_only_feature"},
            ],
            "tasks_md": [
                {"id": "tasks_atomic_actionable",                 "name": "Tasks Atomic and Actionable"},
                {"id": "file_paths_specified",                    "name": "File Paths Specified"},
                {"id": "requirements_traceability_complete",      "name": "Requirements Traceability Complete"},
                {"id": "code_reuse_documented",                   "name": "Code Reuse Documented"},
                {"id": "task_sequencing_respects_dependencies",   "name": "Task Sequencing Respects Dependencies"},
                {"id": "implementation_prompts_structured",       "name": "Implementation Prompts Well-Structured"},
                {"id": "testing_tasks_comprehensive",             "name": "Testing Tasks Comprehensive"},
                {"id": "verification_tasks_cover_removal_parity", "name": "Verification Tasks Cover Removal/Parity",
                 "structural_na_when": "additive_only_feature"},
                {"id": "task_lifecycle_suffix_valid",             "name": "Task Lifecycle Suffix Valid"},
            ],
            "ui_design_md": [
                {"id": "layout_structure_clear",          "name": "Layout Structure Clearly Described"},
                {"id": "component_inventory_complete",    "name": "Component Inventory Complete"},
                {"id": "interaction_patterns_defined",    "name": "Interaction Patterns Defined"},
                {"id": "accessibility_requirements_met",  "name": "Accessibility Requirements Addressed"},
                {"id": "responsive_behavior_specified",   "name": "Responsive Behavior Specified"},
            ],
        },
        "tier1_scripts":       ["spec/lint-tasks.py", "spec/check-traceability.py"],
        "skill_name":          "sdd-review-spec-docs",
        "comprehension_field": "implementation_readiness",
        "extra_doc_fields": {},
    },
    "prd": {
        # doc_files maps type keys to DEFAULT filenames.
        # Actual PRD filenames are flexible (any file matching /prd/i).
        # The skill resolves the real filename; this default is for scoring scaffolding.
        "category": "discovery",
        "doc_keys": ["prd_md"],
        "doc_files": {
            "prd_md": "prd.md",
        },
        "doc_stems": {
            "prd_md": "prd",
        },
        "expected_headings": {
            "prd_md": [
                "Problem Statement",
                "Goals",
                "Functional Requirements",
                "Non-Functional Requirements",
            ],
        },
        "cross_validation_pairs": [],
        "cross_validation_pairs_optional": {
            "prd_md": [],
        },
        "facets": {
            "prd_md": [
                {"id": "problem_statement_clear",          "name": "Problem Statement Clear and Solution-Free"},
                {"id": "goals_measurable_attributable",    "name": "Goals Measurable and Attributable"},
                {"id": "non_goals_reasoned",               "name": "Non-Goals Include Reasons"},
                {"id": "requirements_when_then_format",    "name": "Requirements in WHEN/THEN Format"},
                {"id": "nfrs_all_categories_specific",     "name": "All NFR Categories Specific"},
                {"id": "alternatives_considered_present",  "name": "Alternatives Considered Present"},
                {"id": "open_questions_have_owners",       "name": "Open Questions Have Owners and Blocks"},
                {"id": "rollout_plan_with_gates",          "name": "Rollout Plan Has Success Gates"},
                {"id": "goals_table_complete",              "name": "Goals Table Has Required Columns"},
            ],
        },
        "tier1_scripts":       ["prd/validate-prd.py"],
        "skill_name":          "sdd-review-prd",
        "comprehension_field": "sdd_readiness",
        "extra_doc_fields": {},
    },
}


TYPE_NAMESPACE_MAP: dict = {
    "spec": {
        "context": ["spec_name", "spec_type"],
        "supplemental": ["testing_thoroughness"],
    },
    "steering": {
        "context": [],
        "supplemental": ["design_principles_scorecard"],
    },
    "prd": {
        "context": ["spec_name"],
        "supplemental": ["anti_pattern_detections"],
    },
}


def expected_headings_for_stem(review_type: str, doc_type: str) -> list[str]:
    """Return expected headings for a doc type (e.g. 'ui-design') from the registry."""
    doc_registry = DOCUMENT_REGISTRY.get(review_type)
    if not doc_registry:
        return []
    for doc_key, stem in doc_registry.get("doc_stems", {}).items():
        if stem == doc_type:
            return doc_registry.get("expected_headings", {}).get(doc_key, [])
    return []


def skill_name_for_category(category: str) -> str:
    """Return the review-skill name for the category's review type.

    Routes category -> review type -> skill name through the existing
    registries. Unknown categories raise :class:`KeyError`. The return
    type is :class:`ReviewSkill` (a :class:`str` subclass), so existing
    string consumers keep working while typed callers get structural
    drift protection from the closed enumeration.
    """
    from sdd_core.category_registry import review_type_for_category
    from sdd_core.review_skills import ReviewSkill

    review_type = review_type_for_category(category)
    return ReviewSkill.from_value(DOCUMENT_REGISTRY[review_type]["skill_name"])


def default_doc_list_for_category(category: str) -> str:
    """Return the canonical comma-separated default doc list for *category*.

    Reads ``DOCUMENT_REGISTRY`` so the list stays a single source of
    truth — adding a doc to the registry flows through to every emitter
    that synthesises a default ``--doc-list`` flag. Optional docs are
    excluded from the default because the launch's reviewer cannot
    assume they exist on disk; callers that know they exist can override.

    Routes ``category`` → review type via
    :func:`category_registry.review_type_for_category` so the launch
    contract uses the same dispatch as
    :func:`skill_name_for_category`. Unknown categories raise
    :class:`KeyError`.
    """
    from sdd_core.category_registry import review_type_for_category

    review_type = review_type_for_category(category)
    reg = DOCUMENT_REGISTRY[review_type]
    doc_files = reg["doc_files"]
    return ",".join(doc_files[key] for key in reg["doc_keys"])
