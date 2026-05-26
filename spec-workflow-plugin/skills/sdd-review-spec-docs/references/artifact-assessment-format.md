# Step 9.1: Quality Artifact Assessment Format

> For shared envelope, scores, and conventions see `$SKILLS/sdd-common/references/quality-artifact-base.md`.

## Contents

- [Run Command](#run-command)
- [Summary Fields](#summary-fields)
- [Valid Keys Reference](#valid-keys-reference)

Output this JSON block after the markdown report (Step 9). Include **only** Tier 2 facet scores and readiness results — the script derives all other fields.

**Do NOT include Tier 1 facets** (`task_lifecycle_suffix_valid`, `implementation_prompts_structured`, `requirements_traceability_complete`) — the script scores these from `spec/lint-tasks.py` and `spec/check-traceability.py` and will reject any AI-supplied score for these IDs.

```json
{
  "skill_version": "<version from SKILL.md frontmatter>",
  "spec_name": "<spec-name>",
  "spec_type": "standard|bug-fix",
  "documents_reviewed": ["<doc_key>", ...],
  "tier2_scores": {
    "requirements_md": [ { "id": "<facet_id>", "score": "pass|partial|fail|na", "issues": { "critical": 0, "warning": 0, "suggestion": 0 } } ],
    "design_md": [ ... ],
    "tasks_md": [ ... ]
  },
  "cross_validation": {
    "pairs": {
      "<pair_key>": {
        "conflicts": 0, "duplications": 0, "gaps": 0,
        "findings": [{ "type": "conflict|duplication|gap|drift", "summary": "..." }]
      }
    }
  },
  "testing_thoroughness": {
    "rating": "Comprehensive|Adequate|Basic|Insufficient",
    "summary": ["<per-level observation>", ...]
  },
  "implementation_readiness": {
    "questions": [ { "document": "<doc_key>", "question": "...", "answer_summary": "...", "confidence": "HIGH|MEDIUM|LOW" } ],
    "full_test": { "scenario": "...", "result_summary": "...", "confidence": "HIGH|MEDIUM|LOW" }
  }
}
```

See `$SKILLS/sdd-common/references/quality-artifact-base.md` § Exclusion List for fields the script computes (do NOT include).

## Summary Fields

See `$SKILLS/sdd-common/references/quality-artifact-base.md` § Findings Format for `cross_validation.pairs.findings`.

- **`testing_thoroughness`** — Object: `{ "rating": "...", "summary": ["..."] }`
  - `summary` items: One per testing level (unit → integration → E2E → gaps), each max ~200 chars

## Valid Keys Reference

Use **exactly** these identifiers — the script silently skips unrecognized values.

### Document Keys and Tier 2 Facet IDs

| `doc_key` | Tier 2 Facet IDs (`<facet_id>`) |
|-----------|----------------------------------|
| `requirements_md` | `introduction_clear_context`, `product_vision_alignment`, `user_stories_format`, `acceptance_criteria_testable`, `nonfunctional_requirements_comprehensive`, `dependency_behavior_parity_explicit` |
| `design_md` | `steering_alignment_documented`, `code_reuse_analysis_thorough`, `architecture_clearly_described`, `components_interfaces_defined`, `error_handling_comprehensive`, `testing_strategy_thorough`, `dependency_removal_impact_documented` |
| `tasks_md` | `tasks_atomic_actionable`, `file_paths_specified`, `code_reuse_documented`, `task_sequencing_respects_dependencies`, `testing_tasks_comprehensive`, `verification_tasks_cover_removal_parity` |

**Tier 1 facets** (script-owned — do NOT include): `task_lifecycle_suffix_valid`, `implementation_prompts_structured`, `requirements_traceability_complete`

### Cross-Validation Pair Keys

See `$SKILLS/sdd-common/references/quality-artifact-base.md
§ Cross-Validation Pair Key Format` for the canonical pair-key
separator and the `print-pair-keys.py --type spec` printer recipe.

### Score Values

See `$SKILLS/sdd-common/references/quality-artifact-base.md § Score
Values` for `pass`/`partial`/`fail`/`na` semantics and the
`na_justification` companion field required when `score = "na"`.

### Advisory Cross-Validation at Per-Document Scope

See `$SKILLS/sdd-common/references/quality-artifact-base.md
§ Advisory Cross-Validation` for the shape (``type:
"advisory_cross_validation"``), the routing rule (informational, no
fix-loop entry), and the validator allow-list. Pair-key vocabulary
shares the canonical printer above.

## Run Command

Staging-path recipe: see `$SKILLS/sdd-common/references/quality-artifact-base.md` § Run Command.

```bash
.spec-workflow/sdd review/update-quality.py \
  --type spec \
  --spec-name <spec-name> \
  --doc-dir .spec-workflow/specs/<spec-name> \
  --input .spec-workflow/specs/<spec-name>/.sdd-state/review-assessment-staging.json
```

Confirm the artifact was written to `.spec-workflow/specs/<spec-name>/review-quality.json`.

### Pre-flight commands the workflow already emits

- **Show template** — read
  `pipeline-tick.py --phase pre-launch-check`'s
  `data.template_resolve_commands` map. Emitted by
  `command_templates.template_resolve_command(...)` — one source of
  truth, see `$SKILLS/sdd-common/references/tool-patterns.md
  § Pre-Launch Envelope Contract`.
- **Compliance check (flag form)** —
  `.spec-workflow/sdd review/check-template-compliance.py
  --spec-name {name} --doc requirements.md` (`.md` suffix required;
  the flag is `--template`, not `--template-type` — the
  `did_you_mean` envelope from the script already documents this when
  the agent guesses wrong).
