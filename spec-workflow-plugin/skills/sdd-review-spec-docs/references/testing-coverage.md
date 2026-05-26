# Testing Coverage Assessment

## Criteria Table

| Criterion | Document(s) | Pass/Fail |
|-----------|-------------|-----------|
| Acceptance criteria testable | requirements.md | |
| Testing strategy covers all levels | design.md | |
| Test tasks exist for each level | tasks.md | |
| Test tasks align with strategy | design.md + tasks.md | |
| Test tasks cover all acceptance criteria | requirements.md + tasks.md | |

## Thoroughness Rating

- **Comprehensive**: All criteria pass, full coverage
- **Adequate**: Most pass, minor gaps
- **Basic**: Significant gaps
- **Insufficient**: Missing strategy or tasks

**Summary Breakdown:** For the assessment JSON (Step 9.1), produce a `summary` array alongside the rating with one concise bullet per testing level (unit → integration → E2E) plus any identified gaps. Each item max ~200 chars.

## Tier 1 Deterministic Checks

Before finalizing per-document scores, run the following scripts against the spec documents.
Their exit codes are the **authoritative scores** for these facets — do not override via AI judgment:

| Script | Document(s) | Authoritative facets |
|--------|-------------|---------------------|
| `.spec-workflow/sdd spec/lint-tasks.py --target {spec-name}` | tasks.md | `task_lifecycle_suffix_valid`, `implementation_prompts_structured` |
| `.spec-workflow/sdd spec/check-traceability.py --target {spec-name}` | requirements.md + tasks.md | `requirements_traceability_complete` |

Run each script and record:
- Exit 0 → facet score = `pass`
- Exit 1 → facet score = `fail`

These facet IDs must **not** appear in the `tier2_scores` block you provide in Step 9.1.
The `review/update-quality.py` script runs these scripts itself and will reject any AI-supplied
score for these facet IDs.

**Tier 1 authority:** When `lint-tasks.py` reports `0 failed`, score the
`implementation_prompts_structured` and `task_lifecycle_suffix_valid` facets as
PASS regardless of header task count. Header tasks (organizational groupings
with no implementation content) are intentionally prompt-less — the validator
skips them and reports them as `skipped (header)`.

**Score interpretation:** Tier 2 (subjective) facet scores may vary ±10%
between runs. Treat Tier 1 (validator script) results as authoritative for
pass/fail decisions. Tier 2 findings are supplemental quality signals.
