# Step 7.1: Quality Artifact Assessment Format

> For shared envelope, scores, and conventions see `$SKILLS/sdd-common/references/quality-artifact-base.md`.

Output this JSON block after the markdown report (Step 7). Include **only** Tier 2 facet scores and readiness results — the script derives all other fields.

**Do NOT include Tier 1 facets** — the script scores these from `prd/validate-prd.py` and will reject any AI-supplied score for these IDs. The canonical Tier 1 / Tier 2 split is computed from `TIER1_SCRIPT_SPECS` in `review_quality/constants.py` and emitted in the launch prompt's tier ownership block. See the [Valid Keys Reference](#valid-keys-reference) below for the current split.

```json
{
  "skill_version": "<version from SKILL.md frontmatter>",
  "spec_name": "<feature-name>",
  "documents_reviewed": ["prd_md"],
  "tier2_scores": {
    "prd_md": [
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
  "anti_pattern_detections": [
    { "pattern": "<anti-pattern name>", "section": "<section>", "severity": "Critical|Major|Minor", "detected": true }
  ],
  "sdd_readiness": {
    "questions": [
      { "document": "prd_md", "question": "...", "answer_summary": "...", "confidence": "HIGH|MEDIUM|LOW" }
    ],
    "full_test": { "scenario": "...", "result_summary": "...", "confidence": "HIGH|MEDIUM|LOW" }
  }
}
```

See `$SKILLS/sdd-common/references/quality-artifact-base.md` § Exclusion List for fields the script computes (do NOT include).

## Summary Fields

See `$SKILLS/sdd-common/references/quality-artifact-base.md` § Findings Format for `cross_validation.pairs.findings`.

- **`anti_pattern_detections`** — One entry per anti-pattern scanned. Include only detected patterns (where `detected: true`).

## Valid Keys Reference

Use **exactly** these identifiers — the script silently skips unrecognized values.

### Document Keys and Facet Ownership

| `doc_key` | Tier 2 — AI-scored (include in `tier2_scores`) | Tier 1 — script-owned (do NOT include) |
|-----------|------------------------------------------------|----------------------------------------|
| `prd_md` | `problem_statement_clear`, `goals_measurable_attributable`, `non_goals_reasoned` | `requirements_when_then_format`, `nfrs_all_categories_specific`, `open_questions_have_owners`, `alternatives_considered_present`, `rollout_plan_with_gates`, `goals_table_complete` |

> Canonical source: `TIER1_SCRIPT_SPECS` in `review_quality/constants.py`. The launch prompt also emits this split dynamically.

### Cross-Validation Pair Keys

See `$SKILLS/sdd-common/references/quality-artifact-base.md
§ Cross-Validation Pair Key Format` for the canonical separator and
the `print-pair-keys.py --type prd` printer recipe.

### Score Values

See `$SKILLS/sdd-common/references/quality-artifact-base.md § Score
Values` for `pass`/`partial`/`fail`/`na` semantics and the
`na_justification` companion field required when `score = "na"`.

## Run Command

> **Multi-PRD rule:** `--spec-name` always refers to the discovery project name,
> not individual PRD filenames. See `$SKILLS/sdd-common/references/general-principles.md` § Approval Categories.

Staging-path recipe: see `$SKILLS/sdd-common/references/quality-artifact-base.md` § Run Command.

```bash
.spec-workflow/sdd review/update-quality.py \
  --type prd \
  --spec-name <feature-name> \
  --doc-dir .spec-workflow/discovery/<feature-name> \
  --input .spec-workflow/discovery/<feature-name>/.sdd-state/review-assessment-staging.json
```

Confirm the artifact was written to `.spec-workflow/discovery/<feature-name>/review-quality.json`.
