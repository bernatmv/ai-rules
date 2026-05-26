# PRD Session State Schema

<!-- Schema below must match STEP_SCHEMAS in write-session-state.py -->

Schema version: 1.0.0
File: `.spec-workflow/discovery/{feature}/.prd-session.json`

## Per-Step Required Fields

| Step | Required Keys | Type/Shape |
|------|--------------|------------|
| 1 | `problem_statement.text` | string, ≥2 sentences |
| 2 | `goals` | array of `{id, goal, metric, target, measurement_method}`, ≥2 items |
| 3 | `non_goals` | array of `{id, statement, reason}`; also `in_scope`, `out_of_scope`, `deferred` |
| 4 | `requirements` | array of `{id, priority, text}` (text uses WHEN/THEN format); `nfr_categories` object with keys below |
| 5 | `stress_test.objections_resolved` | boolean; `stress_test.ryg_reds` | array (empty allowed when objections resolved) |

## Step Schema Examples

Use `--show-schema` to get the exact expected shape:

```
.spec-workflow/sdd prd/write-session-state.py --target "{feature-name}" --step N --show-schema
```

**Step 1:**
```json
{"problem_statement": {"text": "<2+ sentences describing the problem>"}}
```

**Step 2:**
```json
{"goals": [{"id": "G1", "goal": "...", "metric": "...", "target": "...", "measurement_method": "..."}]}
```

**Step 3:**
```json
{"in_scope": [...], "out_of_scope": [...], "non_goals": [{"id": "NG1", "statement": "...", "reason": "..."}], "deferred": [...]}
```

**Step 4:**
```json
{"requirements": [{"id": "FR-1", "priority": "P0", "text": "WHEN ... THEN ..."}], "nfr_categories": {"performance": "...", "availability": "...", "scalability": "...", "security": "...", "data_consistency": "...", "observability": "..."}}
```

**Step 5:**
```json
{"stress_test": {"objections": [{"id": "EP-1", "objection": "...", "reference": "...", "resolution": "..."}], "objections_resolved": true, "ryg": {...}, "ryg_reds": [], "ryg_notes": "..."}}
```

## Validation Rules

- Step 1 `problem_statement.text`: must be ≥2 sentences
- Step 2 `goals`: min 2 entries; each requires `id`, `goal`, `metric`, `target`, `measurement_method`
- Step 3 `non_goals`: min 1 entry; each requires `id`, `statement`, `reason`
- Step 4 `requirements`: at least one must contain WHEN/THEN pattern in `text` field
- Step 4 `nfr_categories`: ALL 6 category keys must be present; values are strings (not objects)
- Step 5 `stress_test.objections_resolved`: boolean (not array)
- Step 5 `stress_test.ryg_reds`: array; empty `[]` is accepted when `objections_resolved: true`
