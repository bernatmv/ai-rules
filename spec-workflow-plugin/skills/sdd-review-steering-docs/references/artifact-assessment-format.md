# Step 7.1: Quality Artifact Assessment Format

> For shared envelope, scores, and conventions see `$SKILLS/sdd-common/references/quality-artifact-base.md`.

Output this JSON block after the markdown report (Step 7). Include **only** Tier 2 facet scores and comprehension results — the script derives all other fields.

```json
{
  "skill_version": "<version from SKILL.md frontmatter>",
  "documents_reviewed": ["<doc_key>", ...],
  "tier2_scores": {
    "<doc_key>": [
      { "id": "<facet_id>", "score": "pass|partial|fail|na", "issues": { "critical": 0, "warning": 0, "suggestion": 0 } }
    ]
  },
  "cross_validation": {
    "pairs": {
      "<pair_key>": {
        "conflicts": 0, "duplications": 0, "gaps": 0,
        "findings": [{ "type": "conflict|duplication|gap|drift", "summary": "..." }]
      }
    }
  },
  "design_principles_scorecard": { "ratings": [ { "principle": "...", "rating": "HIGH|MEDIUM|LOW" } ] },
  "ai_comprehension_test": {
    "questions": [ { "document": "<doc_key>", "question": "...", "answer_summary": "...", "confidence": "HIGH|MEDIUM|LOW" } ],
    "full_test": { "scenario": "...", "result_summary": "...", "confidence": "HIGH|MEDIUM|LOW" }
  }
}
```

See `$SKILLS/sdd-common/references/quality-artifact-base.md` § Exclusion List for fields the script computes (do NOT include).

See `$SKILLS/sdd-common/references/quality-artifact-base.md` § Findings Format for `cross_validation.pairs.findings`.

## Valid Keys Reference

Use **exactly** these identifiers — the script silently skips unrecognized values.

### Document Keys and Facet IDs

| `doc_key` | Facet IDs (`<facet_id>`) |
|-----------|--------------------------|
| `product_md` | `product_purpose_stated`, `target_users_described`, `key_features_comprehensive`, `business_objectives_aligned`, `success_metrics_measurable` |
| `tech_md` | `technology_stack_accurate`, `architecture_patterns_described`, `external_integrations_listed`, `performance_requirements_realistic`, `security_considerations_addressed` |
| `structure_md` | `directory_structure_matches_codebase`, `naming_conventions_accurate`, `import_patterns_documented`, `module_boundaries_clear`, `code_organization_reflects_practices` |

### Cross-Validation Pair Keys

See `$SKILLS/sdd-common/references/quality-artifact-base.md
§ Cross-Validation Pair Key Format` for the canonical separator and
the `print-pair-keys.py --type steering` printer recipe.

### Score Values

See `$SKILLS/sdd-common/references/quality-artifact-base.md § Score
Values` for `pass`/`partial`/`fail`/`na` semantics and the
`na_justification` companion field required when `score = "na"`.

## Run Command

Staging-path recipe: see `$SKILLS/sdd-common/references/quality-artifact-base.md` § Run Command.

```bash
.spec-workflow/sdd review/update-quality.py \
  --type steering \
  --doc-dir .spec-workflow/steering \
  --input .spec-workflow/steering/.sdd-state/review-assessment-staging.json
```

Confirm the artifact was written to `.spec-workflow/steering/review-quality.json`.
