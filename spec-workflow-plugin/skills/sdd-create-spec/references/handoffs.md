# sdd-create-spec — Handoffs

Generated from `$SCRIPTS/handoff-registry.json`. Do not hand-edit;
run `.spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite` to regenerate.

| Script | Handoff | Command | Note |
|--------|---------|---------|------|
| `spec/archive.py` | `spec/check-status` | `.spec-workflow/sdd spec/check-status.py --all --workspace {ctx.workspace}` | Confirm the archive transition by listing remaining active specs. |
| `spec/check-status.py` | `review/pipeline-tick:launch` | `.spec-workflow/sdd review/pipeline-tick.py --category spec --target-name "{ctx.target}" --workspace {ctx.workspace} --phase launch -- --review-skill sdd-review-spec-docs --doc-list "requirements.md,design.md,tasks.md" --scope per-document --workflow-mode create` | Open the review pipeline for the spec's current phase. |
| `spec/check-status.py` | `spec/check-status:audit-log-aware` | `.spec-workflow/sdd spec/check-status.py --target {ctx.target} --workspace {ctx.workspace}` | Phase-status check that consults approval-audit.log alongside snapshots. |
| `spec/check-traceability.py` | `review/pipeline-tick:launch` | `.spec-workflow/sdd review/pipeline-tick.py --workspace {ctx.workspace} --category spec --target-name {ctx.target} --phase launch --doc tasks` | Run the review pipeline once full coverage is reported. |
| `spec/detect-context.py` | `spec/check-status` | `.spec-workflow/sdd spec/check-status.py --target {ctx.target} --workspace {ctx.workspace}` | Read the spec's current phase once the workflow context is known. |
| `spec/detect-type.py` | `spec/check-status` | `.spec-workflow/sdd spec/check-status.py --target {ctx.target} --workspace {ctx.workspace}` | Surface the spec's current phase after classification. |
| `spec/lint-design.py` | `review/pipeline-tick:launch` | `.spec-workflow/sdd review/pipeline-tick.py --workspace {ctx.workspace} --category spec --target-name {ctx.target} --phase launch --doc design` | Run the review pipeline once the design lint passes. |
| `spec/lint-requirements.py` | `review/pipeline-tick:launch` | `.spec-workflow/sdd review/pipeline-tick.py --workspace {ctx.workspace} --category spec --target-name {ctx.target} --phase launch --doc requirements` | Run the review pipeline once the requirements lint passes. |
| `spec/lint-requirements.py` | `spec/check-traceability` | `.spec-workflow/sdd spec/check-traceability.py --target {ctx.target} --workspace {ctx.workspace}` | Cross-check requirement IDs against tasks.md once requirements are clean. |
| `spec/lint-tasks.py` | `spec/check-traceability` | `.spec-workflow/sdd spec/check-traceability.py --target {ctx.target} --workspace {ctx.workspace}` | Confirm every requirement in requirements.md has a covering task. |
| `spec/lint-tasks.py` | `review/pipeline-tick:launch` | `.spec-workflow/sdd review/pipeline-tick.py --workspace {ctx.workspace} --category spec --target-name {ctx.target} --phase launch --doc tasks` | Run the review pipeline once tasks lint and traceability are clean. |
