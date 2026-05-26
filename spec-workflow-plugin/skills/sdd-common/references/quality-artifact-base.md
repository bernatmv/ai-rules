# Quality Artifact Base Format

**Schema source of truth:** `sdd_core/review_quality_schema.py` (on-disk envelope) and `sdd_core/review_input.py` (sub-agent input). Import field names from these modules; never restate them.

Shared JSON envelope for review-quality artifacts (spec, PRD, steering).


## Contents

- [Scope](#scope)
- [Shared Envelope](#shared-envelope)
- [Exclusion List](#exclusion-list)
- [Findings Format](#findings-format)
- [Score Values](#score-values)
- [Cross-Validation Pair Key Format](#cross-validation-pair-key-format)
- [Advisory Cross-Validation](#advisory-cross-validation)
- [Run Command](#run-command)
  - [Fold Into review-quality.json](#fold-into-review-qualityjson)
  - [Emitting The Staging Path On Demand](#emitting-the-staging-path-on-demand)

## Scope

This base doc carries **only** envelope-level conventions shared by every
quality artifact:

- Shared JSON envelope shape
- Exclusion list (fields the script computes)
- Findings format
- Score values
- `Run Command` staging-path recipe

Per-review-type conventions **do not** live here. Owners:

| Convention | Owner |
|------------|-------|
| Facet IDs (Tier 1 vs Tier 2 split) | `review_quality/constants.py::TIER1_SCRIPT_SPECS` |
| Cross-validation pair keys + separator | `review_quality/canonical_cross_validation_keys` (emitter: `review_quality/print-pair-keys.py`) |
| Staging file name | `sdd_core/transient_state.py::STAGING_FILENAME` |
| Staging directory | `sdd_core/transient_state.py::STATE_DIR_NAME` |
| Staging path resolver | `review/pipeline_phases/resolvers.py::resolve_staging_path` |

When a convention changes, update the owner — never restate the change in this
document.

## Shared Envelope

All quality artifacts share this structure. Skill-specific fields are documented
in each skill's `artifact-assessment-format.md` reference file.

```json
{
  "schema_version": 3,
  "review_type": "spec|steering|prd",
  "active": {
    "scope": "final|per-document",
    "tier2_scores": {
      "<doc_key>": [
        {
          "id": "<facet_id>",
          "score": "pass|partial|fail",
          "issues": { "critical": 0, "warning": 0, "suggestion": 0 }
        }
      ]
    },
    "cross_validation": {
      "pairs": {
        "<pair_key>": {
          "conflicts": 0,
          "duplications": 0,
          "gaps": 0,
          "findings": [{ "type": "conflict|duplication|gap|drift", "summary": "..." }]
        }
      }
    }
  },
  "by_scope": {
    "per-document": {
      "<doc_key>": {
        "scope": "per-document",
        "tier2_scores": {
          "<doc_key>": [
            {
              "id": "<facet_id>",
              "score": "pass|partial|fail",
              "issues": { "critical": 0, "warning": 0, "suggestion": 0 }
            }
          ]
        }
      }
    },
    "final": {}
  },
  "history": []
}
```

This is the on-disk envelope. The sub-agent INPUT shape (what `update-quality.py --input` accepts) is documented in `sdd_core/review_input.py`.

## Exclusion List

**Do NOT include** in the AI-supplied JSON — the `update-quality.py` script
computes these from the actual files:

`schema_version`, `generated_at`, `overall_score`, `overall_status`, `history`,
`score.value`, `score.max`, `line_count`, `template_compliance`, `size_check`,
or any aggregate.

## Findings Format

- **`cross_validation.pairs.<pair_key>.findings`** — Optional array. Omit when
  the pair has zero issues.
  - `type`: One of `conflict`, `duplication`, `gap`, `drift`
  - `summary`: Concise explanation (max ~200 chars)

## Score Values

`pass` · `partial` · `fail` · `na`

When `score = "na"`, the facet record MUST also carry a non-empty
`na_justification: "<reason>"` field. The validator at
`review_quality/validation.py` rejects the artifact otherwise. See
`review_quality/document_merge.py::merge_facet` for how the field is
preserved through the merge.

A reviewer-supplied `na_justification` keeps the facet in the
denominator (explicit opt-out — half-credit penalty by construction).
The `structural-na:` justification prefix is reserved for the
script-side facet evaluator: facets registered with a
`structural_na_when` predicate in `sdd_core/doc_config.py` (e.g.
removal/parity facets on a purely-additive feature) drop out of both
the numerator *and* the denominator so the artifact score reflects
applicable facets only. The prefix literal is owned by
`review_quality/constants.py::STRUCTURAL_NA_PREFIX`.

## Cross-Validation Pair Key Format

Owned by `review_quality/canonical_cross_validation_keys` — never restate
the separator or literal list in prose. Each review type prints its own
pair-key vocabulary:

```
.spec-workflow/sdd review_quality/print-pair-keys.py --type {spec|steering|prd}
```

Separator is the literal `_x_` (underscore-x-underscore). The
canonical printer (`review_quality/print-pair-keys.py`) is the single
source; never hand-author keys with `__` or `:`.

## Advisory Cross-Validation

A per-doc reviewer that spots a cross-document concern (e.g. timezone
mismatch between requirements and design) can file an **advisory**
finding without requiring `scope=final`. Add the finding to the
relevant pair's `findings` array with `type: "advisory_cross_validation"`.
The finding is informational only — it does not route into the fix
loop — but the final-scope reviewer merges it into the candidate rows
at the next run so the signal is not lost.

Minimal shape:

```json
{
  "type": "advisory_cross_validation",
  "summary": "requirements uses operator-local time; design stores UTC.",
  "detected_at_scope": "per-document",
  "detected_doc": "<doc_key>"
}
```

Validators accept the type via `review_quality.VALID_FINDING_TYPES`.

## Run Command

Stage the assessment JSON at the canonical transient-state path:

```
<doc-dir>/.sdd-state/review-assessment-staging.json
```

`<doc-dir>` is the review's document directory
(`.spec-workflow/specs/<spec-name>/`, `.spec-workflow/steering/`,
`.spec-workflow/discovery/<feature-name>/`). Two writers keep the
path absent before every `Write`:

- Pre-flight (`check_stale_review_staging_files`) deletes residue at
  session start.
- `approval/update-status.py` deletes on every approval outcome via
  `sdd_core.transient_state.cleanup_on_approval`.

### Fold Into `review-quality.json`

```bash
.spec-workflow/sdd review/update-quality.py \
  --type {spec|steering|prd} \
  [--spec-name <spec-name>] \
  --doc-dir <doc-dir> \
  --input <doc-dir>/.sdd-state/review-assessment-staging.json
```

### Emitting The Staging Path On Demand

```
.spec-workflow/sdd review_quality/print-staging-path.py --category <category> [--target-name <name>]
```
